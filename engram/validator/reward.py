"""
Engram Validator — Reward / Weight Setting

Aggregates miner scores and sets Bittensor weights.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from loguru import logger

from engram.validator.scorer import compute_miner_score, normalize_scores


class RewardManager:
    """
    Collects per-miner evaluation results and sets weights on-chain.
    """

    def __init__(self, subtensor: Any, wallet: Any, netuid: int) -> None:
        self._subtensor = subtensor
        self._wallet = wallet
        self._netuid = netuid
        self.moving_averages: dict[int, float] = {}
        self.alpha: float = 0.1  # 10% recent score, 90% historical

    def set_weights(
        self,
        metagraph: Any,
        recall_scores: dict[int, float],          # uid → recall@K
        latency_scores: dict[int, float | None],  # uid → latency_ms
        proof_rates: dict[int, float],            # uid → proof success rate
        slashed_uids: set[int] | None = None,     # uids that failed slash threshold → weight 0
    ) -> bool:
        """
        Compute final scores, normalize, and commit weights to the chain.

        Miners in slashed_uids receive weight 0 regardless of other scores.
        Returns True if weight-setting succeeded.
        """
        uids = list(metagraph.uids.tolist())
        slashed = slashed_uids or set()

        if slashed:
            logger.warning(f"Slashing {len(slashed)} miners with weight=0 | uids={sorted(slashed)}")

        raw_scores: dict[int, float] = {}
        for uid in uids:
            if uid in slashed:
                # Hard zero — slash overrides all other scores
                self.moving_averages[uid] = 0.0
                raw_scores[uid] = 0.0
                continue

            score = compute_miner_score(
                recall=recall_scores.get(uid, 0.0),
                latency_ms=latency_scores.get(uid),
                proof_success_rate=proof_rates.get(uid, 0.0),
            )

            if uid in self.moving_averages:
                self.moving_averages[uid] = self.alpha * score + (1 - self.alpha) * self.moving_averages[uid]
            else:
                self.moving_averages[uid] = score

            raw_scores[uid] = self.moving_averages[uid]

        normalized = normalize_scores({str(uid): s for uid, s in raw_scores.items()})

        weight_uids = np.array(uids, dtype=np.int64)
        weight_vals = np.array(
            [normalized.get(str(uid), 0.0) for uid in uids],
            dtype=np.float32,
        )

        logger.info(
            f"Setting weights | top5={sorted(raw_scores.items(), key=lambda x: -x[1])[:5]}"
        )

        try:
            result = self._subtensor.set_weights(
                netuid=self._netuid,
                wallet=self._wallet,
                uids=weight_uids,
                weights=weight_vals,
                wait_for_inclusion=True,
            )
            if result:
                logger.success("Weights set successfully.")
            else:
                logger.error("Weight setting returned False.")
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to set weights: {e}")
            return False
