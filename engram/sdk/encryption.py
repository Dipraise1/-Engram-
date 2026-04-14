"""
Engram SDK — Client-side Encryption for Private Namespaces

Two encryption schemes are available:

──────────────────────────────────────────────────────────────────────────────
1. NamespaceEncryption  (password-based, legacy)
──────────────────────────────────────────────────────────────────────────────
  - Key derivation: PBKDF2-HMAC-SHA256 (100k iterations, salt = namespace name)
  - Encryption:     AES-256-GCM
  - Wire format:    base64url( iv[12] || ciphertext+tag )
  - Limitation:     One shared key for all messages. Key compromise affects
                    all past and future data.

──────────────────────────────────────────────────────────────────────────────
2. HybridEncryption  (keypair-based, recommended)
──────────────────────────────────────────────────────────────────────────────
  Implements ECDH + HKDF + AES-256-GCM — the same pattern used by Signal,
  age (filippo.io/age), and TLS 1.3.

  Encrypt (per message):
    1. Generate ephemeral X25519 keypair
    2. ECDH(ephemeral_private, recipient_public) → shared_secret
    3. HKDF-SHA256(shared_secret, salt=ephemeral_public, info=b"engram-v1") → 32-byte key
    4. AES-256-GCM encrypt with random 12-byte IV
    5. Wire: base64url( ephemeral_public[32] || iv[12] || ciphertext+tag )

  Decrypt:
    1. Extract ephemeral_public[32] from wire
    2. ECDH(recipient_private, ephemeral_public) → shared_secret
    3. HKDF(same params) → same 32-byte key
    4. AES-256-GCM decrypt

  Properties:
    ✓ Forward secrecy    — ephemeral key per message; past messages safe if key leaked
    ✓ Public key sharing — share public key for writes; private key needed to read
    ✓ No password        — keypair is the identity, nothing to remember/hash
    ✓ Authenticated      — GCM tag detects tampering; ECDH binds to recipient key

Usage:
    # Password-based (backward compatible)
    from engram.sdk.encryption import NamespaceEncryption
    enc = NamespaceEncryption("my-namespace", "my-secret-key")

    # Keypair-based (recommended)
    from engram.sdk.encryption import HybridEncryption, generate_keypair
    private_key, public_key = generate_keypair()   # save private_key securely
    enc = HybridEncryption(private_key=private_key)  # full encrypt+decrypt
    enc = HybridEncryption(public_key=public_key)    # encrypt only (write-only client)

    blob = enc.encrypt_payload("My private text", {"source": "internal"})
    text, meta = enc.decrypt_payload(blob)           # requires private key
"""

from __future__ import annotations

import base64
import json
import os
from typing import Optional

_PBKDF2_ITERATIONS = 100_000
_KEY_LEN    = 32    # AES-256
_IV_LEN     = 12    # GCM nonce
_X25519_LEN = 32    # X25519 public key size
_HKDF_INFO  = b"engram-hybrid-v1"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _aesgcm_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """AES-256-GCM encrypt. Returns iv[12] || ciphertext+tag."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    iv = os.urandom(_IV_LEN)
    return iv + AESGCM(key).encrypt(iv, plaintext, None)


def _aesgcm_decrypt(key: bytes, blob: bytes) -> bytes:
    """AES-256-GCM decrypt. Expects iv[12] || ciphertext+tag."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
    try:
        iv, ct = blob[:_IV_LEN], blob[_IV_LEN:]
        return AESGCM(key).decrypt(iv, ct, None)
    except InvalidTag as exc:
        raise ValueError(
            "Decryption failed — data may be tampered or the key is wrong."
        ) from exc


def _hkdf(shared_secret: bytes, salt: bytes) -> bytes:
    """HKDF-SHA256 — derive a 32-byte AES key from an ECDH shared secret."""
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes
    return HKDF(
        algorithm=hashes.SHA256(),
        length=_KEY_LEN,
        salt=salt,
        info=_HKDF_INFO,
    ).derive(shared_secret)


def _serialize_payload(text: str | None, metadata: dict) -> bytes:
    return json.dumps({"text": text or "", "metadata": metadata}).encode("utf-8")


def _deserialize_payload(data: bytes) -> tuple[str, dict]:
    payload = json.loads(data.decode("utf-8"))
    return payload.get("text", ""), payload.get("metadata", {})


# ── Key generation ────────────────────────────────────────────────────────────

def generate_keypair() -> tuple[bytes, bytes]:
    """
    Generate a fresh X25519 keypair for hybrid encryption.

    Returns:
        (private_key_bytes, public_key_bytes) — each 32 bytes.

    The private key must be kept secret. The public key can be shared freely
    to allow others to encrypt data that only you can decrypt.

    Example::

        private_key, public_key = generate_keypair()
        # Store private_key in a secrets manager or env var
        # Share public_key with anyone who needs to write to your namespace

        enc = HybridEncryption(private_key=private_key)
        blob = enc.encrypt_payload("secret text", {})
        text, meta = enc.decrypt_payload(blob)
    """
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    priv = X25519PrivateKey.generate()
    priv_bytes = priv.private_bytes_raw()
    pub_bytes  = priv.public_key().public_bytes_raw()
    return priv_bytes, pub_bytes


def public_key_from_private(private_key_bytes: bytes) -> bytes:
    """Derive the public key from a private key."""
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    return X25519PrivateKey.from_private_bytes(private_key_bytes).public_key().public_bytes_raw()


# ── Password-based encryption (legacy, backward compatible) ───────────────────

def _derive_key_pbkdf2(namespace: str, namespace_key: str) -> bytes:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_LEN,
        salt=namespace.encode("utf-8"),
        iterations=_PBKDF2_ITERATIONS,
    ).derive(namespace_key.encode("utf-8"))


class NamespaceEncryption:
    """
    Password-based AES-256-GCM encryption for private namespaces.

    Kept for backward compatibility. For new deployments, use HybridEncryption.

    Limitation: one shared key for all messages. Compromise of the namespace_key
    exposes all stored data. No forward secrecy.
    """

    def __init__(self, namespace: str, namespace_key: str) -> None:
        self._key = _derive_key_pbkdf2(namespace, namespace_key)

    def encrypt_payload(self, text: str | None, metadata: dict) -> str:
        blob = _aesgcm_encrypt(self._key, _serialize_payload(text, metadata))
        return base64.urlsafe_b64encode(blob).decode("ascii")

    def decrypt_payload(self, blob: str) -> tuple[str, dict]:
        try:
            raw = base64.urlsafe_b64decode(blob.encode("ascii"))
            return _deserialize_payload(_aesgcm_decrypt(self._key, raw))
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Could not decrypt payload: {exc}") from exc

    def decrypt_results(self, results: list[dict]) -> list[dict]:
        return _decrypt_results(self, results)


# ── Hybrid encryption (X25519 + HKDF + AES-256-GCM) ─────────────────────────

class HybridEncryption:
    """
    Hybrid encryption: X25519 ECDH key exchange + HKDF + AES-256-GCM.

    This is the same scheme used by Signal, age (filippo.io/age), and TLS 1.3.

    Args:
        private_key: 32-byte X25519 private key bytes. Required for decryption.
        public_key:  32-byte X25519 public key bytes. If omitted, derived from
                     private_key. Provide alone for write-only (encrypt-only) clients.

    Wire format per message:
        base64url(
          ephemeral_public[32] ||   # X25519 ephemeral public key
          iv[12]              ||   # AES-GCM nonce
          ciphertext+tag           # AES-256-GCM output (plaintext + 16-byte tag)
        )

    Usage::

        # Full client (read + write)
        private_key, public_key = generate_keypair()
        enc = HybridEncryption(private_key=private_key)

        # Write-only client (can encrypt, cannot decrypt)
        enc = HybridEncryption(public_key=public_key)

        blob = enc.encrypt_payload("secret text", {"source": "db"})
        text, meta = enc.decrypt_payload(blob)   # raises if no private_key
    """

    def __init__(
        self,
        private_key: Optional[bytes] = None,
        public_key:  Optional[bytes] = None,
    ) -> None:
        if private_key is None and public_key is None:
            raise ValueError("HybridEncryption requires at least one of: private_key, public_key")

        self._private_key_bytes = private_key
        if public_key is not None:
            self._public_key_bytes = public_key
        elif private_key is not None:
            self._public_key_bytes = public_key_from_private(private_key)
        else:
            raise ValueError("Cannot derive public key without private key")

    # ── Public API ─────────────────────────────────────────────────────────────

    def encrypt_payload(self, text: str | None, metadata: dict) -> str:
        """
        Encrypt text + metadata. Requires public_key (always available).

        Returns a base64url blob safe to store as JSON metadata.
        Each call generates a fresh ephemeral keypair — forward secrecy.
        """
        from cryptography.hazmat.primitives.asymmetric.x25519 import (
            X25519PrivateKey, X25519PublicKey,
        )

        # 1. Generate ephemeral keypair
        ephemeral_priv = X25519PrivateKey.generate()
        ephemeral_pub  = ephemeral_priv.public_key()
        ephemeral_pub_bytes = ephemeral_pub.public_bytes_raw()

        # 2. ECDH with recipient public key
        recipient_pub = X25519PublicKey.from_public_bytes(self._public_key_bytes)
        shared_secret = ephemeral_priv.exchange(recipient_pub)

        # 3. HKDF: derive AES key (salt = ephemeral public key binds it to this message)
        aes_key = _hkdf(shared_secret, salt=ephemeral_pub_bytes)

        # 4. AES-256-GCM encrypt
        encrypted = _aesgcm_encrypt(aes_key, _serialize_payload(text, metadata))

        # 5. Wire: ephemeral_public || iv || ciphertext+tag
        wire = ephemeral_pub_bytes + encrypted
        return base64.urlsafe_b64encode(wire).decode("ascii")

    def decrypt_payload(self, blob: str) -> tuple[str, dict]:
        """
        Decrypt a blob produced by encrypt_payload. Requires private_key.

        Returns (original_text, original_metadata).
        Raises ValueError if tampered, wrong key, or no private key available.
        """
        if self._private_key_bytes is None:
            raise ValueError(
                "This HybridEncryption instance has no private key — it can encrypt "
                "but not decrypt. Initialise with private_key= to enable decryption."
            )

        from cryptography.hazmat.primitives.asymmetric.x25519 import (
            X25519PrivateKey, X25519PublicKey,
        )

        try:
            raw = base64.urlsafe_b64decode(blob.encode("ascii"))

            # 1. Extract ephemeral public key
            ephemeral_pub_bytes = raw[:_X25519_LEN]
            encrypted           = raw[_X25519_LEN:]

            # 2. ECDH with our private key
            recipient_priv = X25519PrivateKey.from_private_bytes(self._private_key_bytes)
            ephemeral_pub  = X25519PublicKey.from_public_bytes(ephemeral_pub_bytes)
            shared_secret  = recipient_priv.exchange(ephemeral_pub)

            # 3. HKDF — same params as encrypt
            aes_key = _hkdf(shared_secret, salt=ephemeral_pub_bytes)

            # 4. AES-256-GCM decrypt
            plaintext = _aesgcm_decrypt(aes_key, encrypted)
            return _deserialize_payload(plaintext)

        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Could not decrypt hybrid payload: {exc}") from exc

    def decrypt_results(self, results: list[dict]) -> list[dict]:
        return _decrypt_results(self, results)


# ── Shared result decryption ──────────────────────────────────────────────────

def _decrypt_results(enc, results: list[dict]) -> list[dict]:
    """Decrypt _enc field in query results. Works for both encryption classes."""
    out = []
    for r in results:
        meta = r.get("metadata", {})
        blob = meta.get("_enc")
        if blob:
            try:
                _, decrypted_meta = enc.decrypt_payload(blob)
                r = {**r, "metadata": decrypted_meta}
            except ValueError:
                r = {**r, "metadata": {"_error": "decryption_failed"}}
        out.append(r)
    return out
