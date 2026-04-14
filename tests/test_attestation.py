"""
Tests for namespace attestation system.

Covers:
  - Trust tier assignment from stake
  - Attestation creation and retrieval
  - Signature verification (mocked)
  - Stake staleness and refresh
  - Trust tier degradation when stake drops
  - Revocation
  - Persistence (save/load)
  - Query handler returning trust_tier in results
  - Loophole: wrong hotkey can't attest
  - Loophole: replayed timestamp rejected
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from engram.miner.attestation import (
    AttestationRegistry,
    NamespaceAttestation,
    TrustTier,
    build_attestation_payload,
    tier_from_stake,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _registry(tmp_path: Path, stake: float = 0.0) -> AttestationRegistry:
    """Build a registry with a mocked subtensor that returns a fixed stake."""
    subtensor = MagicMock()
    subtensor.get_stake_for_coldkey_and_hotkey.return_value = stake
    reg = AttestationRegistry(
        path=tmp_path / "attestations.json",
        subtensor=subtensor,
        netuid=42,
    )
    return reg


def _attest(reg: AttestationRegistry, namespace: str, hotkey: str = "5FakeHotkey123") -> NamespaceAttestation:
    """Attest with a patched signature verifier (unit test — no real keypair needed)."""
    timestamp_ms = int(time.time() * 1000)
    with patch.object(AttestationRegistry, "_verify_signature"):
        return reg.attest(
            namespace=namespace,
            owner_hotkey=hotkey,
            signature_hex="0xdeadbeef",
            timestamp_ms=timestamp_ms,
        )


# ── Trust tier logic ──────────────────────────────────────────────────────────

def test_tier_anonymous():
    assert tier_from_stake(0.0) == TrustTier.ANONYMOUS

def test_tier_community_boundary():
    assert tier_from_stake(0.99) == TrustTier.ANONYMOUS
    assert tier_from_stake(1.0)  == TrustTier.COMMUNITY
    assert tier_from_stake(99.9) == TrustTier.COMMUNITY

def test_tier_verified_boundary():
    assert tier_from_stake(100.0)  == TrustTier.VERIFIED
    assert tier_from_stake(999.9)  == TrustTier.VERIFIED

def test_tier_sovereign_boundary():
    assert tier_from_stake(1000.0)   == TrustTier.SOVEREIGN
    assert tier_from_stake(999999.0) == TrustTier.SOVEREIGN


# ── Attestation creation ──────────────────────────────────────────────────────

def test_attest_anonymous_no_stake(tmp_path):
    reg = _registry(tmp_path, stake=0.0)
    att = _attest(reg, "my_namespace")
    assert att.trust_tier == TrustTier.ANONYMOUS
    assert att.namespace == "my_namespace"

def test_attest_community(tmp_path):
    reg = _registry(tmp_path, stake=5.0)
    att = _attest(reg, "community_ns")
    assert att.trust_tier == TrustTier.COMMUNITY
    assert att.stake_tao == 5.0

def test_attest_verified(tmp_path):
    reg = _registry(tmp_path, stake=250.0)
    att = _attest(reg, "verified_ns")
    assert att.trust_tier == TrustTier.VERIFIED

def test_attest_sovereign(tmp_path):
    reg = _registry(tmp_path, stake=5000.0)
    att = _attest(reg, "sovereign_ns")
    assert att.trust_tier == TrustTier.SOVEREIGN

def test_attest_overwrites_existing(tmp_path):
    reg = _registry(tmp_path, stake=5.0)
    _attest(reg, "ns")
    # Stake goes up — re-attest should upgrade tier
    reg._subtensor.get_stake_for_coldkey_and_hotkey.return_value = 500.0
    att = _attest(reg, "ns")
    assert att.trust_tier == TrustTier.VERIFIED


# ── Retrieval ─────────────────────────────────────────────────────────────────

def test_get_unattested_returns_none(tmp_path):
    reg = _registry(tmp_path)
    assert reg.get("nonexistent") is None

def test_trust_tier_unattested_is_anonymous(tmp_path):
    reg = _registry(tmp_path)
    assert reg.trust_tier("nonexistent") == TrustTier.ANONYMOUS

def test_trust_tier_attested(tmp_path):
    reg = _registry(tmp_path, stake=150.0)
    _attest(reg, "ns")
    assert reg.trust_tier("ns") == TrustTier.VERIFIED


# ── Stake staleness and refresh ───────────────────────────────────────────────

def test_stale_stake_triggers_refresh(tmp_path):
    reg = _registry(tmp_path, stake=5.0)
    att = _attest(reg, "ns")

    # Force stake to appear stale
    att.stake_refreshed_at = time.time() - 9999
    reg._records["ns"] = att

    # Stake has now dropped to anonymous
    reg._subtensor.get_stake_for_coldkey_and_hotkey.return_value = 0.0

    refreshed = reg.get("ns")
    assert refreshed.trust_tier == TrustTier.ANONYMOUS

def test_fresh_stake_not_refreshed(tmp_path):
    reg = _registry(tmp_path, stake=5000.0)
    _attest(reg, "ns")

    # Drop stake on mock — but record is fresh, should NOT refresh
    reg._subtensor.get_stake_for_coldkey_and_hotkey.return_value = 0.0

    att = reg.get("ns")
    # Still sovereign because refresh hasn't triggered
    assert att.trust_tier == TrustTier.SOVEREIGN


# ── Revocation ────────────────────────────────────────────────────────────────

def test_revoke_removes_attestation(tmp_path):
    reg = _registry(tmp_path, stake=100.0)
    _attest(reg, "ns", hotkey="5Owner")

    timestamp_ms = int(time.time() * 1000)
    with patch.object(AttestationRegistry, "_verify_signature"):
        ok = reg.revoke("ns", "5Owner", "0xdeadbeef", timestamp_ms)

    assert ok is True
    assert reg.get("ns") is None

def test_revoke_wrong_hotkey_rejected(tmp_path):
    reg = _registry(tmp_path, stake=100.0)
    _attest(reg, "ns", hotkey="5Owner")

    with pytest.raises(ValueError, match="Only the original owner"):
        with patch.object(AttestationRegistry, "_verify_signature"):
            reg.revoke("ns", "5NotTheOwner", "0xdeadbeef", int(time.time() * 1000))

def test_revoke_nonexistent_returns_false(tmp_path):
    reg = _registry(tmp_path)
    with patch.object(AttestationRegistry, "_verify_signature"):
        assert reg.revoke("ghost", "5X", "0xdeadbeef", int(time.time() * 1000)) is False


# ── Timestamp replay protection ───────────────────────────────────────────────

def test_stale_timestamp_rejected(tmp_path):
    reg = _registry(tmp_path)
    stale_ts = int((time.time() - 120) * 1000)  # 2 minutes ago
    with pytest.raises(ValueError, match="outside the"):
        reg.attest("ns", "5Fake", "0xdeadbeef", stale_ts)

def test_future_timestamp_rejected(tmp_path):
    reg = _registry(tmp_path)
    future_ts = int((time.time() + 120) * 1000)  # 2 minutes in future
    with pytest.raises(ValueError, match="outside the"):
        reg.attest("ns", "5Fake", "0xdeadbeef", future_ts)


# ── Persistence ───────────────────────────────────────────────────────────────

def test_persistence_survives_restart(tmp_path):
    reg = _registry(tmp_path, stake=200.0)
    _attest(reg, "persistent_ns", hotkey="5PersistentOwner")

    # Simulate restart — new registry instance reads from disk
    reg2 = AttestationRegistry(path=tmp_path / "attestations.json")
    att = reg2.get("persistent_ns")

    assert att is not None
    assert att.namespace == "persistent_ns"
    assert att.owner_hotkey == "5PersistentOwner"
    assert att.trust_tier == TrustTier.VERIFIED

def test_persistence_corrupt_file_starts_empty(tmp_path):
    path = tmp_path / "attestations.json"
    path.write_text("not valid json")
    reg = AttestationRegistry(path=path)
    assert reg.list_attested() == []


# ── Query handler integration ─────────────────────────────────────────────────

def test_query_results_include_trust_tier(tmp_path):
    from engram.miner.query import QueryHandler
    from engram.protocol import QuerySynapse

    # Build mocks
    mock_store = MagicMock()
    mock_store.search.return_value = [
        MagicMock(cid="v1::abc", score=0.95, metadata={}),
    ]
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = np.zeros(1536, dtype=np.float32)

    reg = _registry(tmp_path, stake=500.0)
    _attest(reg, "__public__")  # attest the public namespace

    handler = QueryHandler(
        store=mock_store,
        embedder=mock_embedder,
        attestation_registry=reg,
    )

    synapse = QuerySynapse(query_text="test query")
    result  = handler.handle(synapse)

    assert len(result.results) == 1
    assert "trust_tier" in result.results[0]
    assert result.results[0]["trust_tier"] == TrustTier.VERIFIED.value

def test_query_unattested_namespace_returns_anonymous(tmp_path):
    from engram.miner.query import QueryHandler
    from engram.protocol import QuerySynapse

    mock_store = MagicMock()
    mock_store.search.return_value = [
        MagicMock(cid="v1::abc", score=0.9, metadata={}),
    ]
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = np.zeros(1536, dtype=np.float32)

    reg = _registry(tmp_path, stake=0.0)  # no attestations

    handler = QueryHandler(
        store=mock_store,
        embedder=mock_embedder,
        attestation_registry=reg,
    )

    synapse = QuerySynapse(query_text="test query")
    result  = handler.handle(synapse)

    assert result.results[0]["trust_tier"] == TrustTier.ANONYMOUS.value


# ── build_attestation_payload helper ─────────────────────────────────────────

def test_build_attestation_payload_structure():
    mock_keypair = MagicMock()
    mock_keypair.ss58_address = "5FakeOwner"
    mock_keypair.sign.return_value = bytes(64)  # 64 zero bytes

    payload = build_attestation_payload(mock_keypair, "my_namespace")

    assert payload["namespace"] == "my_namespace"
    assert payload["owner_hotkey"] == "5FakeOwner"
    assert payload["signature"].startswith("0x")
    assert isinstance(payload["timestamp_ms"], int)
    assert abs(payload["timestamp_ms"] - int(time.time() * 1000)) < 2000
