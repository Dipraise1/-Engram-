"""
Engram Validator — Scorer

Computes a [0, 1] score for each miner based on:
  recall@K  (quality)
  latency   (speed)
  proof rate (storage honesty)

Final score = α·recall + β·latency_score + γ·proof_rate
"""

from __future__ import annotations

import numpy as np

from engram.config import (
    LATENCY_BASELINE_MS,
    LATENCY_TARGET_MS,
    RECALL_K,
    SCORE_ALPHA,
    SCORE_BETA,
    SCORE_GAMMA,
)


def recall_at_k(
    returned_cids: list[str],
    ground_truth_cids: list[str],
    k: int = RECALL_K,
) -> float:
    """
    Compute recall@K.
    What fraction of the true top-K results did the miner return?
    """
    if not ground_truth_cids:
        return 0.0
    top_k_returned = set(returned_cids[:k])
    top_k_truth = set(ground_truth_cids[:k])
    hits = len(top_k_returned & top_k_truth)
    return hits / min(k, len(top_k_truth))


def latency_score(latency_ms: float | None) -> float:
    """
    Map latency to a [0, 1] score.
    LATENCY_TARGET_MS or below → 1.0
    LATENCY_BASELINE_MS or above → 0.0
    Linear interpolation in between.
    """
    if latency_ms is None:
        return 0.0
    if latency_ms <= LATENCY_TARGET_MS:
        return 1.0
    if latency_ms >= LATENCY_BASELINE_MS:
        return 0.0
    return 1.0 - (latency_ms - LATENCY_TARGET_MS) / (LATENCY_BASELINE_MS - LATENCY_TARGET_MS)


def compute_miner_score(
    recall: float,
    latency_ms: float | None,
    proof_success_rate: float,
) -> float:
    """
    Weighted final score for one miner.

    Args:
        recall:             recall@K from the last query evaluation
        latency_ms:         query latency reported by the miner (or measured by validator)
        proof_success_rate: fraction of storage challenges the miner passed (0.0–1.0)

    Returns:
        float in [0, 1]
    """
    r = float(np.clip(recall, 0.0, 1.0))
    l = float(np.clip(latency_score(latency_ms), 0.0, 1.0))
    p = float(np.clip(proof_success_rate, 0.0, 1.0))

    return SCORE_ALPHA * r + SCORE_BETA * l + SCORE_GAMMA * p


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """
    Normalize a uid→score dict so scores sum to 1.0 (for Bittensor weight setting).
    Miners with score 0 stay at 0.
    """
    if not scores:
        return {}
    total = sum(scores.values())
    if total == 0:
        return {uid: 0.0 for uid in scores}
    return {uid: s / total for uid, s in scores.items()}
