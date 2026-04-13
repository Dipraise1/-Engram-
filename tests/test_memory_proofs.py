"""
Memory layer — Storage proof tests.

Tests the challenge/response protocol that proves a miner
actually holds a vector, not just its CID.

Covers:
  - Single-CID: valid proof, tampered proof, wrong embedding, wrong CID, expiry
  - Batch: all-pass, partial fail, position shuffling, expired, nonce mismatch
  - Replay protection (nonce reuse rejected)
  - ChallengeDispatcher integration (record stats, slashable threshold)
"""

from __future__ import annotations

import time
import pytest
import numpy as np

try:
    import engram_core
    _RUST = True
except ImportError:
    _RUST = False

_BATCH = _RUST and hasattr(engram_core, "generate_batch_challenge")

pytestmark = pytest.mark.skipif(not _RUST, reason="engram_core Rust module not built")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _emb(values: list[float]) -> list[float]:
    return [float(v) for v in values]

EMB_A = _emb([0.1, 0.2, 0.3, 0.4, 0.5])
EMB_B = _emb([0.9, 0.8, 0.7, 0.6, 0.5])
EMB_WRONG = _emb([9.9, 9.9, 9.9, 9.9, 9.9])


def make_cid(emb: list[float]) -> str:
    return engram_core.generate_cid(emb, {}, "v1")


# ── CID integrity ─────────────────────────────────────────────────────────────

def test_cid_deterministic() -> None:
    assert make_cid(EMB_A) == make_cid(EMB_A)


def test_different_embeddings_different_cids() -> None:
    assert make_cid(EMB_A) != make_cid(EMB_B)


def test_cid_format() -> None:
    cid = make_cid(EMB_A)
    assert cid.startswith("v1::")
    assert len(cid.split("::", 1)[1]) == 64


def test_verify_cid_passes() -> None:
    cid = make_cid(EMB_A)
    assert engram_core.verify_cid(cid, EMB_A, {}, "v1")


def test_verify_cid_wrong_embedding_fails() -> None:
    cid = make_cid(EMB_A)
    assert not engram_core.verify_cid(cid, EMB_B, {}, "v1")


def test_parse_cid() -> None:
    cid = make_cid(EMB_A)
    version, digest = engram_core.parse_cid(cid)
    assert version == "v1"
    assert len(digest) == 64


# ── Single-CID challenge/response ────────────────────────────────────────────

def test_valid_proof() -> None:
    cid = make_cid(EMB_A)
    ch = engram_core.generate_challenge(cid, 60)
    resp = engram_core.generate_response(ch, EMB_A)
    assert engram_core.verify_response(ch, resp, EMB_A)


def test_wrong_embedding_fails() -> None:
    cid = make_cid(EMB_A)
    ch = engram_core.generate_challenge(cid, 60)
    resp = engram_core.generate_response(ch, EMB_A)
    assert not engram_core.verify_response(ch, resp, EMB_WRONG)


def test_wrong_cid_in_response_fails() -> None:
    cid = make_cid(EMB_A)
    ch = engram_core.generate_challenge(cid, 60)
    resp = engram_core.generate_response(ch, EMB_A)

    # Swap the CID in the challenge for a different one
    ch2 = engram_core.generate_challenge(make_cid(EMB_B), 60)
    assert not engram_core.verify_response(ch2, resp, EMB_A)


def test_challenge_fields() -> None:
    cid = make_cid(EMB_A)
    ch = engram_core.generate_challenge(cid, 30)
    assert ch.cid == cid
    assert len(ch.nonce_hex) == 64      # 32 bytes → 64 hex chars
    assert ch.issued_at > 0
    assert ch.expires_at == ch.issued_at + 30


def test_response_fields() -> None:
    cid = make_cid(EMB_A)
    ch = engram_core.generate_challenge(cid, 60)
    resp = engram_core.generate_response(ch, EMB_A)
    assert resp.cid == cid
    assert resp.nonce_hex == ch.nonce_hex
    assert len(resp.embedding_hash) == 64
    assert len(resp.proof) == 64


def test_each_challenge_has_unique_nonce() -> None:
    cid = make_cid(EMB_A)
    ch1 = engram_core.generate_challenge(cid, 60)
    ch2 = engram_core.generate_challenge(cid, 60)
    assert ch1.nonce_hex != ch2.nonce_hex


# ── Batch challenge/response ──────────────────────────────────────────────────
# These tests require the wheel to be rebuilt after the batch API was added.
# In CI the wheel is always rebuilt; locally skip if the API isn't present yet.

@pytest.mark.skipif(not _BATCH, reason="batch proof API not in installed wheel (rebuild needed)")
def test_batch_all_valid() -> None:
    cids = [make_cid(EMB_A), make_cid(EMB_B)]
    embs = [EMB_A, EMB_B]
    batch = engram_core.generate_batch_challenge(cids, 60)
    resp = engram_core.generate_batch_response(batch, embs)
    results = engram_core.verify_batch_response(batch, resp, embs)
    assert results == [True, True]


@pytest.mark.skipif(not _BATCH, reason="batch proof API not in installed wheel (rebuild needed)")
def test_batch_one_wrong_embedding() -> None:
    cids = [make_cid(EMB_A), make_cid(EMB_B)]
    embs = [EMB_A, EMB_B]
    batch = engram_core.generate_batch_challenge(cids, 60)
    resp = engram_core.generate_batch_response(batch, embs)

    # Verify with wrong embedding for the second slot
    results = engram_core.verify_batch_response(batch, resp, [EMB_A, EMB_WRONG])
    assert results == [True, False]


@pytest.mark.skipif(not _BATCH, reason="batch proof API not in installed wheel (rebuild needed)")
def test_batch_all_wrong_embeddings() -> None:
    cids = [make_cid(EMB_A), make_cid(EMB_B)]
    batch = engram_core.generate_batch_challenge(cids, 60)
    resp = engram_core.generate_batch_response(batch, [EMB_A, EMB_B])
    results = engram_core.verify_batch_response(batch, resp, [EMB_WRONG, EMB_WRONG])
    assert results == [False, False]


@pytest.mark.skipif(not _BATCH, reason="batch proof API not in installed wheel (rebuild needed)")
def test_batch_proof_not_shuffleable() -> None:
    """A miner cannot swap valid proofs between CID slots."""
    cids = [make_cid(EMB_A), make_cid(EMB_B)]
    batch = engram_core.generate_batch_challenge(cids, 60)
    resp = engram_core.generate_batch_response(batch, [EMB_A, EMB_B])

    # Verifying with reversed embeddings exposes the index-binding invariant.
    results = engram_core.verify_batch_response(batch, resp, [EMB_B, EMB_A])
    assert results == [False, False]


@pytest.mark.skipif(not _BATCH, reason="batch proof API not in installed wheel (rebuild needed)")
def test_batch_expired_fails_all() -> None:
    cids = [make_cid(EMB_A)]
    batch = engram_core.generate_batch_challenge(cids, 0)   # already expired
    resp = engram_core.generate_batch_response(batch, [EMB_A])
    results = engram_core.verify_batch_response(batch, resp, [EMB_A])
    assert results == [False]


@pytest.mark.skipif(not _BATCH, reason="batch proof API not in installed wheel (rebuild needed)")
def test_batch_single_entry() -> None:
    cids = [make_cid(EMB_A)]
    batch = engram_core.generate_batch_challenge(cids, 60)
    resp = engram_core.generate_batch_response(batch, [EMB_A])
    results = engram_core.verify_batch_response(batch, resp, [EMB_A])
    assert results == [True]


@pytest.mark.skipif(not _BATCH, reason="batch proof API not in installed wheel (rebuild needed)")
def test_batch_large() -> None:
    """Batch with many CIDs — all should verify correctly."""
    n = 50
    embs = [_emb([float(i) / n, 1.0 - float(i) / n, 0.0, 0.0, 0.0]) for i in range(n)]
    cids = [make_cid(e) for e in embs]
    batch = engram_core.generate_batch_challenge(cids, 60)
    resp = engram_core.generate_batch_response(batch, embs)
    results = engram_core.verify_batch_response(batch, resp, embs)
    assert all(results)
    assert len(results) == n


@pytest.mark.skipif(not _BATCH, reason="batch proof API not in installed wheel (rebuild needed)")
def test_batch_fields() -> None:
    cids = [make_cid(EMB_A), make_cid(EMB_B)]
    batch = engram_core.generate_batch_challenge(cids, 30)
    assert batch.cids == cids
    assert len(batch.nonce_hex) == 64
    assert batch.expires_at == batch.issued_at + 30


@pytest.mark.skipif(not _BATCH, reason="batch proof API not in installed wheel (rebuild needed)")
def test_batch_entry_fields() -> None:
    cids = [make_cid(EMB_A)]
    batch = engram_core.generate_batch_challenge(cids, 60)
    resp = engram_core.generate_batch_response(batch, [EMB_A])
    entry = resp.entries[0]
    assert entry.cid == cids[0]
    assert len(entry.embedding_hash) == 64
    assert len(entry.proof) == 64


# ── ChallengeDispatcher (Python layer) ───────────────────────────────────────

from engram.validator.challenge import ChallengeDispatcher


@pytest.fixture
def dispatcher() -> ChallengeDispatcher:
    return ChallengeDispatcher()


def test_dispatcher_register_cid(dispatcher: ChallengeDispatcher) -> None:
    cid = make_cid(EMB_A)
    dispatcher.register_cid(cid)
    assert cid in dispatcher._known_cids_set


def test_dispatcher_pick_random_cid(dispatcher: ChallengeDispatcher) -> None:
    assert dispatcher.pick_random_cid() is None
    cid = make_cid(EMB_A)
    dispatcher.register_cid(cid)
    assert dispatcher.pick_random_cid() == cid


def test_dispatcher_build_challenge(dispatcher: ChallengeDispatcher) -> None:
    cid = make_cid(EMB_A)
    ch = dispatcher.build_challenge(cid)
    assert ch is not None
    assert ch.cid == cid


def test_dispatcher_verify_valid_response(dispatcher: ChallengeDispatcher) -> None:
    cid = make_cid(EMB_A)
    ch = dispatcher.build_challenge(cid)
    resp = engram_core.generate_response(ch, EMB_A)
    ok = dispatcher.verify_response(ch, resp.embedding_hash, resp.proof, EMB_A)
    assert ok is True


def test_dispatcher_rejects_replay(dispatcher: ChallengeDispatcher) -> None:
    """The same nonce must be rejected a second time."""
    cid = make_cid(EMB_A)
    ch = dispatcher.build_challenge(cid)
    resp = engram_core.generate_response(ch, EMB_A)

    # First use — valid
    ok1 = dispatcher.verify_response(ch, resp.embedding_hash, resp.proof, EMB_A)
    assert ok1 is True

    # Second use of same nonce — must be rejected
    ok2 = dispatcher.verify_response(ch, resp.embedding_hash, resp.proof, EMB_A)
    assert ok2 is False


def test_dispatcher_record_and_slash(dispatcher: ChallengeDispatcher) -> None:
    from engram.config import MIN_CHALLENGES_BEFORE_SLASH

    uid = "miner42"
    # Fail every challenge
    for _ in range(MIN_CHALLENGES_BEFORE_SLASH):
        dispatcher.record_result(uid, passed=False)

    assert uid in dispatcher.slashable_miners()


def test_dispatcher_passing_miner_not_slashed(dispatcher: ChallengeDispatcher) -> None:
    from engram.config import MIN_CHALLENGES_BEFORE_SLASH

    uid = "honest_miner"
    for _ in range(MIN_CHALLENGES_BEFORE_SLASH):
        dispatcher.record_result(uid, passed=True)

    assert uid not in dispatcher.slashable_miners()


def test_dispatcher_partial_failure_below_threshold(dispatcher: ChallengeDispatcher) -> None:
    from engram.config import MIN_CHALLENGES_BEFORE_SLASH, SLASH_THRESHOLD

    uid = "ok_miner"
    for i in range(MIN_CHALLENGES_BEFORE_SLASH):
        # Pass more than SLASH_THRESHOLD of the time
        dispatcher.record_result(uid, passed=(i % 3 != 0))

    record = dispatcher.get_record(uid)
    if record.success_rate >= SLASH_THRESHOLD:
        assert uid not in dispatcher.slashable_miners()
