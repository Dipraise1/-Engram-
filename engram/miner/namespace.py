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


class NamespaceRegistry:
    """
    Thread-safe registry of private namespaces.

    Each namespace entry stores:
      - key_hash: PBKDF2 hash of the user's secret key
      - created_at: Unix timestamp
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
