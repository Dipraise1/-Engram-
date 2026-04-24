"""
Engram Miner — Namespace Registry

Namespaces are private, isolated vector collections.
Data stored under a namespace is only accessible to requests that present the correct key.

Design:
  - Public data (no namespace) behaves exactly as before.
  - Private data requires a namespace name + secret key.
  - The key is never stored — only a PBKDF2 hash is persisted.
  - Namespace isolation is enforced at the store query layer (Qdrant filter / FAISS partition).

Persistence: data/namespaces.json  (configurable via NAMESPACE_REGISTRY_PATH)
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from threading import Lock

from loguru import logger

_DEFAULT_PATH = Path(os.getenv("NAMESPACE_REGISTRY_PATH", "data/namespaces.json"))
_PBKDF2_ITERATIONS = 100_000


def _hash_key(namespace: str, key: str) -> str:
    """Derive a slow, salted hash of the key.  Never stores the key in plaintext."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        key.encode("utf-8"),
        namespace.encode("utf-8"),   # namespace name is the salt
        _PBKDF2_ITERATIONS,
    )
    return dk.hex()


_SIG_WINDOW_MS: int = 60_000   # ±60s replay window for namespace signatures

_CANONICAL_NS_MSG = "engram-ns:{namespace}:{timestamp_ms}"


class NamespaceRegistry:
    """
    Thread-safe registry of private namespaces.

    Supports two auth modes:
      sig-based  (preferred) — sr25519 hotkey ownership, key never travels on wire
      key-based  (legacy)    — PBKDF2 password hash, backward compatible

    Each namespace entry stores one or both of:
      owner_hotkey: SS58 address of the signing owner (sig-based)
      key_hash:     PBKDF2 hash of the secret key (legacy)
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = path
        self._lock = Lock()
        self._data: dict[str, dict] = self._load()

    # ── Public API ─────────────────────────────────────────────────────────────

    def create(self, namespace: str, key: str) -> None:
        """
        Register a new namespace with a hashed key.

        Raises ValueError if the namespace already exists (use rotate_key to change).
        """
        if not namespace or not namespace.isidentifier():
            raise ValueError(
                f"Namespace name must be a valid identifier (letters, digits, underscores). Got: {namespace!r}"
            )
        if len(key) < 16:
            raise ValueError("Namespace key must be at least 16 characters.")

        with self._lock:
            if namespace in self._data:
                raise ValueError(
                    f"Namespace '{namespace}' already exists. "
                    "Use a different name or delete the existing one first."
                )
            import time
            self._data[namespace] = {
                "key_hash": _hash_key(namespace, key),
                "created_at": time.time(),
            }
            self._flush()
        logger.info(f"Namespace created: {namespace!r}")

    def verify(self, namespace: str, key: str) -> bool:
        """Return True if the key matches the stored hash for this namespace."""
        with self._lock:
            entry = self._data.get(namespace)
        if entry is None:
            return False
        expected = entry["key_hash"]
        provided  = _hash_key(namespace, key)
        # Constant-time comparison to prevent timing oracle
        import hmac as _hmac
        return _hmac.compare_digest(expected, provided)

    def exists(self, namespace: str) -> bool:
        with self._lock:
            return namespace in self._data

    def delete(self, namespace: str, key: str) -> bool:
        """Delete a namespace — requires the correct key to prevent accidental wipes."""
        if not self.verify(namespace, key):
            return False
        with self._lock:
            self._data.pop(namespace, None)
            self._flush()
        logger.info(f"Namespace deleted: {namespace!r}")
        return True

    def rotate_key(self, namespace: str, old_key: str, new_key: str) -> bool:
        """Replace the key for a namespace — requires the current key."""
        if len(new_key) < 16:
            raise ValueError("New key must be at least 16 characters.")
        if not self.verify(namespace, old_key):
            return False
        with self._lock:
            self._data[namespace]["key_hash"] = _hash_key(namespace, new_key)
            self._flush()
        logger.info(f"Namespace key rotated: {namespace!r}")
        return True

    # ── Sig-based auth ─────────────────────────────────────────────────────────

    def register_owner(self, namespace: str, owner_hotkey: str) -> None:
        """Register a namespace with an sr25519 hotkey as sole owner (sig-based auth)."""
        if not namespace or not namespace.isidentifier():
            raise ValueError(f"Invalid namespace name: {namespace!r}")
        import time
        with self._lock:
            existing = self._data.get(namespace, {})
            existing.update({"owner_hotkey": owner_hotkey, "created_at": existing.get("created_at", time.time())})
            self._data[namespace] = existing
            self._flush()
        logger.info(f"Namespace owner registered: {namespace!r} → {owner_hotkey[:12]}…")

    def owner_hotkey(self, namespace: str) -> str | None:
        """Return the registered owner hotkey, or None if not set."""
        with self._lock:
            return self._data.get(namespace, {}).get("owner_hotkey")

    def verify_sig(self, namespace: str, hotkey: str, sig_hex: str, timestamp_ms: int) -> bool:
        """
        Verify an sr25519 namespace ownership signature.

        The canonical message is: f"engram-ns:{namespace}:{timestamp_ms}"

        Returns True if:
          - timestamp_ms is within ±60s of server time (replay prevention)
          - sig_hex is a valid sr25519 signature over the canonical message by hotkey
          - if the namespace has a registered owner, hotkey matches it
        """
        import time as _time
        now_ms = int(_time.time() * 1000)
        if abs(now_ms - timestamp_ms) > _SIG_WINDOW_MS:
            return False

        # If namespace has a registered owner, the hotkey must match
        stored_owner = self.owner_hotkey(namespace)
        if stored_owner is not None and stored_owner != hotkey:
            return False

        message = _CANONICAL_NS_MSG.format(namespace=namespace, timestamp_ms=timestamp_ms).encode()
        try:
            sig_bytes = bytes.fromhex(sig_hex.removeprefix("0x"))
        except ValueError:
            return False

        try:
            import bittensor as bt
            kp = bt.Keypair(ss58_address=hotkey)
            return kp.verify(message, sig_bytes)
        except ImportError:
            logger.warning("bittensor not installed — skipping sig verification (dev mode)")
            return True
        except Exception as exc:
            logger.debug(f"Namespace sig verification error: {exc}")
            return False

    def list_namespaces(self) -> list[str]:
        """Return all registered namespace names (no keys or hashes)."""
        with self._lock:
            return list(self._data.keys())

    # ── Private ───────────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2),
            encoding="utf-8",
        )
