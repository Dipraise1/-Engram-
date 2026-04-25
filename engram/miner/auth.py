"""
Engram Miner — Hotkey Signature Verification

Verifies that HTTP requests are signed by the claimed Bittensor hotkey.
Prevents hotkey spoofing (e.g. claiming a high-stake validator's hotkey
to bypass stake checks or inflate wallet-tracker stats).

Protocol
--------
The caller adds three fields to every request body:

    {
      "hotkey":    "5F...",          # SS58 address of the signing keypair
      "nonce":     1712345678123,    # unix ms — replay protection
      "signature": "0xabc123...",   # hex sr25519 sig over canonical message
      ...payload...
    }

Canonical message (UTF-8 bytes):
    f"{nonce}:{endpoint}:{body_hash}"

where body_hash is the SHA-256 hex of the JSON-serialised *payload* fields
(everything except hotkey/nonce/signature themselves), sorted by key.

Replay window: ±30 seconds from server time (covers reasonable clock skew).

Configuration
-------------
REQUIRE_HOTKEY_SIG=true   — reject requests with missing/invalid signatures
REQUIRE_HOTKEY_SIG=false  — warn but allow (default; backward compatible)

ALLOWED_VALIDATOR_HOTKEYS=5F...,5G...  (comma-separated SS58 addresses)
  Enforce a strict allowlist on top of signature verification.

REQUIRE_METAGRAPH_REG=true   — reject hotkeys not registered on the subnet
REQUIRE_METAGRAPH_REG=false  — warn but allow (default)
NETUID / SUBTENSOR_NETWORK   — used for metagraph registration checks
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Any

from loguru import logger

# ── Config ────────────────────────────────────────────────────────────────────

from engram.config import ENGRAM_ENV
_sig_default = "true" if ENGRAM_ENV == "mainnet" else "false"
REQUIRE_SIG: bool = os.getenv("REQUIRE_HOTKEY_SIG", _sig_default).lower() == "true"
REPLAY_WINDOW_SECS: float = 30.0

_raw_allowlist = os.getenv("ALLOWED_VALIDATOR_HOTKEYS", "").strip()
ALLOWED_HOTKEYS: set[str] | None = (
    {h.strip() for h in _raw_allowlist.split(",") if h.strip()}
    if _raw_allowlist
    else None
)

REQUIRE_METAGRAPH_REG: bool = os.getenv("REQUIRE_METAGRAPH_REG", "false").lower() == "true"
_NETUID = int(os.getenv("NETUID", "450"))
_NETWORK = os.getenv("SUBTENSOR_ENDPOINT") or os.getenv("SUBTENSOR_NETWORK", "test")

# ── Metagraph registration cache ──────────────────────────────────────────────
# Refreshed at most once per METAGRAPH_CACHE_TTL_SECS to avoid hammering the chain.

_METAGRAPH_CACHE_TTL_SECS: float = 300.0
_metagraph_hotkeys: set[str] = set()
_metagraph_last_refresh: float = 0.0
_refresh_lock = threading.Lock()


def _refresh_metagraph() -> None:
    """Pull registered hotkeys from the Bittensor metagraph into the local cache.
    Runs in a background daemon thread — never blocks the caller."""
    if not _refresh_lock.acquire(blocking=False):
        return  # another thread is already refreshing
    try:
        global _metagraph_hotkeys, _metagraph_last_refresh
        import bittensor as bt
        subtensor = bt.Subtensor(network=_NETWORK)
        metagraph = subtensor.metagraph(netuid=_NETUID)
        _metagraph_hotkeys = {axon.hotkey for axon in metagraph.axons if axon.hotkey}
        _metagraph_last_refresh = time.time()
        logger.debug(f"Metagraph cache refreshed | {len(_metagraph_hotkeys)} hotkeys on netuid={_NETUID}")
    except Exception as exc:
        logger.warning(f"Metagraph refresh failed — keeping stale cache: {exc}")
    finally:
        _refresh_lock.release()


def _is_registered(hotkey: str) -> bool:
    """Return True if the hotkey is registered on the subnet (cached, refreshed every 5 min)."""
    if time.time() - _metagraph_last_refresh > _METAGRAPH_CACHE_TTL_SECS:
        threading.Thread(target=_refresh_metagraph, daemon=True).start()
    return hotkey in _metagraph_hotkeys


# ── Bittensor keypair import (optional dep) ───────────────────────────────────

def _bt_keypair_verify(ss58_address: str, message: bytes, signature: bytes) -> bool:
    """Verify a sr25519 signature using the bittensor Keypair."""
    try:
        import bittensor as bt
        kp = bt.Keypair(ss58_address=ss58_address)
        return kp.verify(message, signature)
    except Exception as exc:
        logger.debug(f"Signature verification error for {ss58_address[:12]}…: {exc}")
        return False


# ── Canonical message ─────────────────────────────────────────────────────────

def _payload_hash(body: dict[str, Any]) -> str:
    """SHA-256 of the payload fields (excludes hotkey/nonce/signature), sorted."""
    payload = {k: v for k, v in body.items() if k not in ("hotkey", "nonce", "signature")}
    serialised = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialised.encode()).hexdigest()


def _canonical_message(nonce: int, endpoint: str, body: dict[str, Any]) -> bytes:
    body_hash = _payload_hash(body)
    return f"{nonce}:{endpoint}:{body_hash}".encode()


# ── Public API ────────────────────────────────────────────────────────────────

class AuthError(Exception):
    """Raised when a request fails authentication."""


def verify_request(body: dict[str, Any], endpoint: str) -> str | None:
    """
    Verify the hotkey signature on an incoming request body.

    Returns the verified hotkey string on success, or None if no hotkey was
    provided (anonymous request).

    Raises AuthError if:
    - REQUIRE_HOTKEY_SIG=true and signature is missing/invalid
    - Hotkey is not in ALLOWED_HOTKEYS (when allowlist is configured)
    - Nonce is outside the replay window
    """
    hotkey: str | None = body.get("hotkey")
    nonce: int | None = body.get("nonce")
    signature: str | None = body.get("signature")

    # ── Allowlist check (independent of signature requirement) ────────────────
    if ALLOWED_HOTKEYS is not None and hotkey is not None:
        if hotkey not in ALLOWED_HOTKEYS:
            raise AuthError(
                f"Hotkey {hotkey[:12]}… is not in the allowed-validator list. "
                "Ask the miner operator to add your hotkey to ALLOWED_VALIDATOR_HOTKEYS."
            )

    # ── Metagraph registration check ──────────────────────────────────────────
    # Ensures the caller is actually registered on the subnet, not just any
    # key that happened to pass signature verification.
    if hotkey is not None:
        if not _is_registered(hotkey):
            if REQUIRE_METAGRAPH_REG:
                raise AuthError(
                    f"Hotkey {hotkey[:12]}… is not registered on subnet {_NETUID}. "
                    f"Register with: btcli subnet register --netuid {_NETUID}"
                )
            logger.warning(f"Unregistered hotkey {hotkey[:12]}… (REQUIRE_METAGRAPH_REG=false — allowing)")

    # ── No signature provided ─────────────────────────────────────────────────
    if hotkey is None or nonce is None or signature is None:
        if REQUIRE_SIG:
            raise AuthError(
                "This miner requires signed requests. "
                "Include hotkey, nonce (unix ms), and signature in the request body."
            )
        # Soft mode — allow but warn so operators know traffic is unsigned
        if hotkey:
            logger.debug(f"Unsigned request from hotkey={hotkey[:12]}…")
        return hotkey

    # ── Replay protection ─────────────────────────────────────────────────────
    now_ms = int(time.time() * 1000)
    if abs(now_ms - nonce) > REPLAY_WINDOW_SECS * 1000:
        raise AuthError(
            f"Nonce {nonce} is outside the ±{int(REPLAY_WINDOW_SECS)}s replay window. "
            "Check that your system clock is synchronised."
        )

    # ── Signature verification ────────────────────────────────────────────────
    message = _canonical_message(nonce, endpoint, body)
    try:
        sig_bytes = bytes.fromhex(signature.removeprefix("0x"))
    except ValueError:
        raise AuthError("Signature must be a hex string (with or without 0x prefix).")

    if not _bt_keypair_verify(hotkey, message, sig_bytes):
        if REQUIRE_SIG:
            raise AuthError(
                f"Signature verification failed for hotkey {hotkey[:12]}…. "
                "Ensure you are signing with the correct keypair."
            )
        logger.warning(
            f"Invalid signature from hotkey={hotkey[:12]}… endpoint={endpoint} — "
            "proceeding (REQUIRE_HOTKEY_SIG=false)"
        )
        return hotkey

    logger.debug(f"Signature verified | hotkey={hotkey[:12]}… | endpoint={endpoint}")
    return hotkey


# ── Signing helper (for use in validator / SDK) ───────────────────────────────

def sign_request(
    keypair,  # bt.Keypair
    endpoint: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """
    Add hotkey/nonce/signature fields to a request body dict.

    Usage in validator:
        payload = sign_request(wallet.hotkey, "QuerySynapse", {"query_vector": [...], "top_k": 10})
        resp = http_post(url, payload)
    """
    nonce = int(time.time() * 1000)
    body_with_hotkey = {**body, "hotkey": keypair.ss58_address, "nonce": nonce}
    message = _canonical_message(nonce, endpoint, body_with_hotkey)
    sig_hex = "0x" + keypair.sign(message).hex()
    return {**body_with_hotkey, "signature": sig_hex}
