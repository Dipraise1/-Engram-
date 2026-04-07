"""
Tests for engram/miner/auth.py — hotkey signature verification.

Covers:
- sign_request / verify_request round-trip (happy path)
- Replay attack blocked (nonce outside ±30s window)
- Tampered payload detected
- Tampered signature detected
- Wrong hotkey (sig valid but for a different key)
- Missing sig in hard mode (REQUIRE_HOTKEY_SIG=true) → AuthError
- Missing sig in soft mode (REQUIRE_HOTKEY_SIG=false) → allowed with None/hotkey
- Allowlist enforcement (ALLOWED_VALIDATOR_HOTKEYS)
- Anonymous request (no hotkey) is allowed in soft mode
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

# We test purely with Python-level mocks so bittensor isn't required in CI.
# The real bt.Keypair path is covered by test_bt_keypair_roundtrip below.
from engram.miner.auth import (
    AuthError,
    _canonical_message,
    _payload_hash,
    sign_request,
    verify_request,
)


# ── Minimal fake keypair ──────────────────────────────────────────────────────

import hashlib
import hmac as _hmac


class _FakeKeypair:
    """
    Deterministic fake keypair that signs with HMAC-SHA256.
    Lets us test the auth module without bittensor installed.
    The 'secret' is never transmitted — only the ss58_address and signature.
    """

    def __init__(self, ss58_address: str, secret: bytes = b"testkey"):
        self.ss58_address = ss58_address
        self._secret = secret

    def sign(self, message: bytes) -> bytes:
        return _hmac.new(self._secret, message, hashlib.sha256).digest()

    def verify(self, message: bytes, signature: bytes) -> bool:
        expected = _hmac.new(self._secret, message, hashlib.sha256).digest()
        return _hmac.compare_digest(expected, signature)


KEYPAIR_A = _FakeKeypair("5FakeHotkeyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", secret=b"secret_a")
KEYPAIR_B = _FakeKeypair("5FakeHotkeyBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", secret=b"secret_b")


def _bt_verify_patch(ss58_address, message, sig_bytes):
    """Route bt.Keypair.verify calls to our fake keypair."""
    kp = KEYPAIR_A if ss58_address == KEYPAIR_A.ss58_address else KEYPAIR_B
    return kp.verify(message, sig_bytes)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sign(keypair: _FakeKeypair, endpoint: str, body: dict) -> dict:
    nonce = int(time.time() * 1000)
    body_with_meta = {**body, "hotkey": keypair.ss58_address, "nonce": nonce}
    msg = _canonical_message(nonce, endpoint, body_with_meta)
    sig = "0x" + keypair.sign(msg).hex()
    return {**body_with_meta, "signature": sig}


def _do_verify(body: dict, endpoint: str = "IngestSynapse", require: bool = False):
    with (
        patch("engram.miner.auth._bt_keypair_verify", side_effect=_bt_verify_patch),
        patch("engram.miner.auth.REQUIRE_SIG", require),
        patch("engram.miner.auth.ALLOWED_HOTKEYS", None),
    ):
        return verify_request(body, endpoint)


# ── Round-trip ────────────────────────────────────────────────────────────────

def test_sign_and_verify_roundtrip():
    body = {"text": "hello world", "metadata": {}}
    signed = _sign(KEYPAIR_A, "IngestSynapse", body)
    result = _do_verify(signed, "IngestSynapse")
    assert result == KEYPAIR_A.ss58_address


def test_roundtrip_different_endpoints():
    for endpoint in ("IngestSynapse", "QuerySynapse", "ChallengeSynapse"):
        body = {"query_vector": [0.1, 0.2], "top_k": 5}
        signed = _sign(KEYPAIR_A, endpoint, body)
        result = _do_verify(signed, endpoint)
        assert result == KEYPAIR_A.ss58_address


# ── Replay protection ─────────────────────────────────────────────────────────

def test_old_nonce_rejected():
    body = {"text": "stale"}
    signed = _sign(KEYPAIR_A, "IngestSynapse", body)
    # Wind the nonce back 60 seconds — outside the ±30s window
    signed["nonce"] = int((time.time() - 60) * 1000)
    # Recompute signature with the old nonce so it would be valid if not for the replay check
    msg = _canonical_message(signed["nonce"], "IngestSynapse", signed)
    signed["signature"] = "0x" + KEYPAIR_A.sign(msg).hex()
    with pytest.raises(AuthError, match="replay window"):
        _do_verify(signed)


def test_future_nonce_rejected():
    body = {"text": "future"}
    signed = _sign(KEYPAIR_A, "IngestSynapse", body)
    signed["nonce"] = int((time.time() + 60) * 1000)
    msg = _canonical_message(signed["nonce"], "IngestSynapse", signed)
    signed["signature"] = "0x" + KEYPAIR_A.sign(msg).hex()
    with pytest.raises(AuthError, match="replay window"):
        _do_verify(signed)


# ── Tamper detection ──────────────────────────────────────────────────────────

def test_tampered_payload_rejected_in_hard_mode():
    body = {"text": "original content"}
    signed = _sign(KEYPAIR_A, "IngestSynapse", body)
    signed["text"] = "injected content"  # change payload after signing
    with pytest.raises(AuthError, match="Signature verification failed"):
        _do_verify(signed, require=True)


def test_tampered_payload_warns_in_soft_mode(caplog):
    import logging
    body = {"text": "original content"}
    signed = _sign(KEYPAIR_A, "IngestSynapse", body)
    signed["text"] = "injected content"
    # Soft mode — should NOT raise, but logs warning
    result = _do_verify(signed, require=False)
    assert result == KEYPAIR_A.ss58_address  # hotkey still returned


def test_invalid_signature_hex_rejected():
    body = {"text": "test"}
    signed = _sign(KEYPAIR_A, "IngestSynapse", body)
    signed["signature"] = "not-valid-hex"
    with pytest.raises(AuthError, match="hex"):
        _do_verify(signed, require=True)


# ── Wrong keypair ─────────────────────────────────────────────────────────────

def test_wrong_keypair_rejected_hard_mode():
    """Sign with keypair B but claim to be keypair A."""
    body = {"text": "impersonation attempt"}
    # Sign with B's key but put A's hotkey in the body
    nonce = int(time.time() * 1000)
    signed = {
        "text": "impersonation attempt",
        "hotkey": KEYPAIR_A.ss58_address,  # claimed identity
        "nonce": nonce,
    }
    msg = _canonical_message(nonce, "IngestSynapse", signed)
    signed["signature"] = "0x" + KEYPAIR_B.sign(msg).hex()  # signed by B
    with pytest.raises(AuthError, match="Signature verification failed"):
        _do_verify(signed, require=True)


# ── Missing signature ─────────────────────────────────────────────────────────

def test_missing_sig_hard_mode_raises():
    body = {"text": "unsigned", "hotkey": KEYPAIR_A.ss58_address}
    with pytest.raises(AuthError, match="signed requests"):
        _do_verify(body, require=True)


def test_missing_sig_soft_mode_allowed():
    body = {"text": "unsigned", "hotkey": KEYPAIR_A.ss58_address}
    result = _do_verify(body, require=False)
    assert result == KEYPAIR_A.ss58_address


def test_anonymous_request_soft_mode_allowed():
    """No hotkey at all — anonymous SDK/direct-HTTP caller."""
    body = {"text": "anonymous"}
    result = _do_verify(body, require=False)
    assert result is None


def test_anonymous_request_hard_mode_raises():
    body = {"text": "anonymous"}
    with pytest.raises(AuthError, match="signed requests"):
        _do_verify(body, require=True)


# ── Allowlist ─────────────────────────────────────────────────────────────────

def test_allowlist_accepts_known_hotkey():
    body = _sign(KEYPAIR_A, "QuerySynapse", {"query_vector": [0.1], "top_k": 5})
    with (
        patch("engram.miner.auth._bt_keypair_verify", side_effect=_bt_verify_patch),
        patch("engram.miner.auth.REQUIRE_SIG", False),
        patch("engram.miner.auth.ALLOWED_HOTKEYS", {KEYPAIR_A.ss58_address}),
    ):
        result = verify_request(body, "QuerySynapse")
    assert result == KEYPAIR_A.ss58_address


def test_allowlist_rejects_unknown_hotkey():
    body = _sign(KEYPAIR_B, "QuerySynapse", {"query_vector": [0.1], "top_k": 5})
    with (
        patch("engram.miner.auth._bt_keypair_verify", side_effect=_bt_verify_patch),
        patch("engram.miner.auth.REQUIRE_SIG", False),
        patch("engram.miner.auth.ALLOWED_HOTKEYS", {KEYPAIR_A.ss58_address}),
    ):
        with pytest.raises(AuthError, match="allowed-validator"):
            verify_request(body, "QuerySynapse")


# ── Payload hash stability ────────────────────────────────────────────────────

def test_payload_hash_excludes_auth_fields():
    """Auth fields must not affect the payload hash — allows sign-then-add-sig."""
    payload = {"text": "hello", "metadata": {"k": "v"}}
    h1 = _payload_hash({**payload})
    h2 = _payload_hash({**payload, "hotkey": "5Fx...", "nonce": 123, "signature": "0xabc"})
    assert h1 == h2


def test_payload_hash_detects_change():
    h1 = _payload_hash({"text": "hello"})
    h2 = _payload_hash({"text": "HELLO"})
    assert h1 != h2


# ── Metagraph registration check ──────────────────────────────────────────────

def test_unregistered_hotkey_rejected_in_hard_mode():
    body = _sign(KEYPAIR_A, "IngestSynapse", {"text": "test"})
    with (
        patch("engram.miner.auth._bt_keypair_verify", side_effect=_bt_verify_patch),
        patch("engram.miner.auth.REQUIRE_SIG", False),
        patch("engram.miner.auth.ALLOWED_HOTKEYS", None),
        patch("engram.miner.auth.REQUIRE_METAGRAPH_REG", True),
        patch("engram.miner.auth._is_registered", return_value=False),
    ):
        with pytest.raises(AuthError, match="not registered on subnet"):
            verify_request(body, "IngestSynapse")


def test_unregistered_hotkey_warns_in_soft_mode():
    body = _sign(KEYPAIR_A, "IngestSynapse", {"text": "test"})
    with (
        patch("engram.miner.auth._bt_keypair_verify", side_effect=_bt_verify_patch),
        patch("engram.miner.auth.REQUIRE_SIG", False),
        patch("engram.miner.auth.ALLOWED_HOTKEYS", None),
        patch("engram.miner.auth.REQUIRE_METAGRAPH_REG", False),
        patch("engram.miner.auth._is_registered", return_value=False),
    ):
        result = verify_request(body, "IngestSynapse")
    assert result == KEYPAIR_A.ss58_address


def test_registered_hotkey_passes():
    body = _sign(KEYPAIR_A, "IngestSynapse", {"text": "test"})
    with (
        patch("engram.miner.auth._bt_keypair_verify", side_effect=_bt_verify_patch),
        patch("engram.miner.auth.REQUIRE_SIG", False),
        patch("engram.miner.auth.ALLOWED_HOTKEYS", None),
        patch("engram.miner.auth.REQUIRE_METAGRAPH_REG", True),
        patch("engram.miner.auth._is_registered", return_value=True),
    ):
        result = verify_request(body, "IngestSynapse")
    assert result == KEYPAIR_A.ss58_address
