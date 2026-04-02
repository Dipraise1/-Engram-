"""Edge-case tests for reward moving-average behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from engram.validator.reward import RewardManager


def _metagraph_with_uids(uids: list[int]) -> MagicMock:
    metagraph = MagicMock()
    metagraph.uids = np.array(uids)
    return metagraph


def test_new_miner_initializes_moving_average() -> None:
    subtensor = MagicMock()
    subtensor.set_weights.return_value = True
    wallet = MagicMock()
    manager = RewardManager(subtensor, wallet, netuid=1)
    metagraph = _metagraph_with_uids([1])

    ok = manager.set_weights(
        metagraph=metagraph,
        recall_scores={1: 0.8},
        latency_scores={1: 150.0},
        proof_rates={1: 0.9},
    )

    assert ok is True
    assert 1 in manager.moving_averages
    first_value = manager.moving_averages[1]
    assert 0.0 <= first_value <= 1.0


def test_existing_miner_uses_exponential_smoothing() -> None:
    subtensor = MagicMock()
    subtensor.set_weights.return_value = True
    wallet = MagicMock()
    manager = RewardManager(subtensor, wallet, netuid=1)
    metagraph = _metagraph_with_uids([7])

    manager.set_weights(
        metagraph=metagraph,
        recall_scores={7: 1.0},
        latency_scores={7: 100.0},
        proof_rates={7: 1.0},
    )
    first_value = manager.moving_averages[7]
    assert first_value > 0.0

    manager.set_weights(
        metagraph=metagraph,
        recall_scores={7: 0.0},
        latency_scores={7: 500.0},
        proof_rates={7: 0.0},
    )
    second_value = manager.moving_averages[7]

    assert 0.0 < second_value < first_value
    # With alpha=0.1 and a new score of 0, we expect a 10% decay.
    assert second_value == pytest.approx(first_value * 0.9)


def test_missing_round_defaults_to_zero_and_decays() -> None:
    subtensor = MagicMock()
    subtensor.set_weights.return_value = True
    wallet = MagicMock()
    manager = RewardManager(subtensor, wallet, netuid=1)
    metagraph = _metagraph_with_uids([11])

    manager.set_weights(
        metagraph=metagraph,
        recall_scores={11: 1.0},
        latency_scores={11: 100.0},
        proof_rates={11: 1.0},
    )
    first_value = manager.moving_averages[11]

    # Miner remains in metagraph but has no current-round metrics.
    manager.set_weights(
        metagraph=metagraph,
        recall_scores={},
        latency_scores={},
        proof_rates={},
    )
    second_value = manager.moving_averages[11]

    assert second_value == pytest.approx(first_value * 0.9)
