"""Tests for the validator scoring functions."""

import pytest

from engram.validator.scorer import (
    compute_miner_score,
    latency_score,
    normalize_scores,
    recall_at_k,
)


def test_recall_perfect():
    assert recall_at_k(["a", "b", "c"], ["a", "b", "c"], k=3) == 1.0


def test_recall_zero():
    assert recall_at_k(["x", "y", "z"], ["a", "b", "c"], k=3) == 0.0


def test_recall_partial():
    score = recall_at_k(["a", "x", "b"], ["a", "b", "c"], k=3)
    assert pytest.approx(score, 0.01) == 2 / 3


def test_recall_empty_truth():
    assert recall_at_k(["a", "b"], [], k=3) == 0.0


def test_latency_at_target():
    assert latency_score(100.0) == 1.0


def test_latency_at_baseline():
    assert latency_score(500.0) == 0.0


def test_latency_none():
    assert latency_score(None) == 0.0


def test_latency_interpolated():
    # midpoint between 100 and 500 = 300ms → 0.5
    score = latency_score(300.0)
    assert pytest.approx(score, 0.01) == 0.5


def test_compute_score_bounds():
    score = compute_miner_score(recall=0.8, latency_ms=150.0, proof_success_rate=0.9)
    assert 0.0 <= score <= 1.0


def test_compute_score_perfect():
    score = compute_miner_score(recall=1.0, latency_ms=50.0, proof_success_rate=1.0)
    assert pytest.approx(score, 0.001) == 1.0


def test_normalize_scores():
    scores = {"a": 0.5, "b": 0.3, "c": 0.2}
    normed = normalize_scores(scores)
    assert pytest.approx(sum(normed.values()), 0.001) == 1.0


def test_normalize_all_zero():
    scores = {"a": 0.0, "b": 0.0}
    normed = normalize_scores(scores)
    assert all(v == 0.0 for v in normed.values())
