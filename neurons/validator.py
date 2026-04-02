"""
Engram — Validator Neuron

Periodically:
  1. Queries miners with ground truth vectors → scores recall@K
  2. Issues storage proof challenges → tracks proof success rate
  3. Sets weights on-chain via Bittensor
"""

import os
import time

import bittensor as bt
import numpy as np
from dotenv import load_dotenv
from loguru import logger

from engram.config import CHALLENGE_INTERVAL_SECS, RECALL_K, SUBNET_VERSION
from engram.miner.embedder import get_embedder
from engram.protocol import ChallengeSynapse, QuerySynapse
from engram.validator.challenge import ChallengeDispatcher
from engram.validator.ground_truth import GroundTruthManager
from engram.validator.reward import RewardManager
from engram.validator.scorer import recall_at_k
from engram.utils.logging import setup_logging

load_dotenv()
setup_logging(os.getenv("LOG_LEVEL", "INFO"))

EVAL_INTERVAL = 120   # seconds between scoring rounds
WEIGHT_INTERVAL = 600 # seconds between weight-setting


def main() -> None:
    wallet_name = os.getenv("WALLET_NAME", "default")
    wallet_hotkey = os.getenv("WALLET_HOTKEY", "default")
    network = os.getenv("SUBTENSOR_ENDPOINT") or os.getenv("SUBTENSOR_NETWORK", "test")
    netuid = int(os.getenv("NETUID", "99"))
    gt_path = os.getenv("GROUND_TRUTH_PATH", "./data/ground_truth.jsonl")

    logger.info(f"Engram Validator v{SUBNET_VERSION} | network={network} | netuid={netuid}")

    # ── Bittensor setup ───────────────────────────────────────────────────────
    wallet = bt.Wallet(name=wallet_name, hotkey=wallet_hotkey)
    subtensor = bt.Subtensor(network=network)
    metagraph = subtensor.metagraph(netuid=netuid)
    dendrite = bt.Dendrite(wallet=wallet)

    # ── Components ────────────────────────────────────────────────────────────
    embedder = get_embedder()
    ground_truth = GroundTruthManager(path=gt_path)
    challenge_dispatcher = ChallengeDispatcher()
    reward_manager = RewardManager(subtensor=subtensor, wallet=wallet, netuid=netuid)

    # Register known CIDs for challenges
    for cid in ground_truth.all_cids():
        challenge_dispatcher.register_cid(cid)

    logger.info(f"Ground truth entries: {len(ground_truth)}")

    # ── Per-miner tracking ────────────────────────────────────────────────────
    recall_scores: dict[int, float] = {}
    latency_scores: dict[int, float | None] = {}

    last_eval = 0.0
    last_weight_set = 0.0
    last_challenge = 0.0

    # ── Main loop ─────────────────────────────────────────────────────────────
    try:
        while True:
            now = time.time()
            metagraph.sync(subtensor=subtensor)
            axons = metagraph.axons
            uids = metagraph.uids.tolist()

            # ── Scoring round ─────────────────────────────────────────────────
            if now - last_eval >= EVAL_INTERVAL:
                last_eval = now
                sample = ground_truth.sample(n=5)

                for entry in sample:
                    query_syn = QuerySynapse(
                        query_vector=entry.embedding.tolist(),
                        top_k=RECALL_K,
                    )
                    responses = dendrite.query(
                        axons=axons,
                        synapse=query_syn,
                        deserialize=False,
                        timeout=30,
                    )

                    for uid, response in zip(uids, responses):
                        if response is None or response.error:
                            recall_scores[uid] = 0.0
                            latency_scores[uid] = None
                            continue

                        # Be defensive about miner response shape to avoid crashes.
                        returned = [
                            r.get("cid")
                            for r in (response.results or [])
                            if isinstance(r, dict) and r.get("cid") is not None
                        ]
                        r = recall_at_k(returned, entry.top_k_cids, k=RECALL_K)
                        recall_scores[uid] = r
                        latency_scores[uid] = response.latency_ms

                logger.info(f"Eval round complete | miners={len(uids)}")

            # ── Challenge round ───────────────────────────────────────────────
            if now - last_challenge >= CHALLENGE_INTERVAL_SECS:
                last_challenge = now
                cid = challenge_dispatcher.pick_random_cid()

                if cid:
                    entry = next((e for e in ground_truth._entries if e.cid == cid), None)
                    challenge = challenge_dispatcher.build_challenge(cid)

                    if challenge and entry is not None:
                        challenge_syn = ChallengeSynapse(
                            cid=challenge.cid,
                            nonce_hex=challenge.nonce_hex,
                            expires_at=challenge.expires_at,
                        )
                        responses = dendrite.query(
                            axons=axons,
                            synapse=challenge_syn,
                            deserialize=False,
                            timeout=15,
                        )

                        for uid, response in zip(uids, responses):
                            if response is None or response.error:
                                challenge_dispatcher.record_result(str(uid), passed=False)
                                continue

                            passed = challenge_dispatcher.verify_response(
                                challenge=challenge,
                                response_embedding_hash=response.embedding_hash or "",
                                response_proof=response.proof or "",
                                expected_embedding=entry.embedding.tolist(),
                            )
                            challenge_dispatcher.record_result(str(uid), passed=passed)

            # ── Weight setting ────────────────────────────────────────────────
            if now - last_weight_set >= WEIGHT_INTERVAL:
                last_weight_set = now
                # Only use proof records for miners that have actually been challenged.
                # Miners with no challenges get a neutral 0.0 proof rate instead of 1.0.
                proof_rates: dict[int, float] = {}
                for uid in uids:
                    record = challenge_dispatcher._records.get(str(uid))  # type: ignore[attr-defined]
                    proof_rates[int(uid)] = record.success_rate if record else 0.0
                reward_manager.set_weights(
                    metagraph=metagraph,
                    recall_scores=recall_scores,
                    latency_scores=latency_scores,
                    proof_rates=proof_rates,
                )

            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Validator shutting down.")


if __name__ == "__main__":
    main()
