"""
Engram SDK — Client-side Encryption for Private Namespaces

When a namespace + namespace_key are set on EngramClient, ALL data is encrypted
client-side before being sent to any miner. Miners store ciphertext only — they
never see the original text or metadata.

Scheme:
  - Key derivation: PBKDF2-HMAC-SHA256 (100k iterations, salt = namespace name)
  - Encryption:     AES-256-GCM  (authenticated encryption — tampering detected)
  - IV:             Random 12-byte nonce per message
  - Wire format:    base64url( iv[12] || tag[16] || ciphertext )

Semantic search still works because the embedding (float32 vector) is stored
unencrypted — only the text and metadata are encrypted.

Usage (internal — called automatically by EngramClient when namespace is set):
    from engram.sdk.encryption import NamespaceEncryption
    enc = NamespaceEncryption("my-namespace", "my-secret-key")
    blob = enc.encrypt_payload("My private text", {"source": "internal"})
    text, meta = enc.decrypt_payload(blob)
"""

from __future__ import annotations

import base64
import json
import os

_PBKDF2_ITERATIONS = 100_000
_KEY_LEN = 32       # AES-256
_IV_LEN  = 12       # GCM nonce
_TAG_LEN = 16       # GCM auth tag


def _derive_key(namespace: str, namespace_key: str) -> bytes:
    """Derive a 32-byte AES key from the namespace key using PBKDF2."""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_LEN,
        salt=namespace.encode("utf-8"),
        iterations=_PBKDF2_ITERATIONS,
    )
    return kdf.derive(namespace_key.encode("utf-8"))


class NamespaceEncryption:
    """
    Handles AES-256-GCM encryption/decryption for a single namespace.

    Create one instance per (namespace, namespace_key) pair and reuse it —
    key derivation runs once at construction.
    """

    def __init__(self, namespace: str, namespace_key: str) -> None:
        self._key = _derive_key(namespace, namespace_key)

    def encrypt_payload(self, text: str | None, metadata: dict) -> str:
        """
        Encrypt text + metadata into an opaque base64 blob.

        Returns a base64url string safe to store in JSON metadata.
        """
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        plaintext = json.dumps({
            "text": text or "",
            "metadata": metadata,
        }).encode("utf-8")
        iv = os.urandom(_IV_LEN)
        aesgcm = AESGCM(self._key)
        ciphertext_and_tag = aesgcm.encrypt(iv, plaintext, None)
        # wire format: iv || ciphertext+tag
        blob = iv + ciphertext_and_tag
        return base64.urlsafe_b64encode(blob).decode("ascii")

    def decrypt_payload(self, blob: str) -> tuple[str, dict]:
        """
        Decrypt a blob produced by encrypt_payload.

        Returns (original_text, original_metadata).
        Raises ValueError if the blob is tampered or the key is wrong.
        """
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.exceptions import InvalidTag
        try:
            raw = base64.urlsafe_b64decode(blob.encode("ascii"))
            iv              = raw[:_IV_LEN]
            ciphertext_tag  = raw[_IV_LEN:]
            aesgcm          = AESGCM(self._key)
            plaintext       = aesgcm.decrypt(iv, ciphertext_tag, None)
            payload         = json.loads(plaintext.decode("utf-8"))
            return payload.get("text", ""), payload.get("metadata", {})
        except InvalidTag as exc:
            raise ValueError(
                "Decryption failed — the data may be corrupted or the namespace key is wrong."
            ) from exc
        except Exception as exc:
            raise ValueError(f"Could not decrypt payload: {exc}") from exc

    def decrypt_results(self, results: list[dict]) -> list[dict]:
        """
        Decrypt the _enc field in a list of query results in-place.
        Results without _enc are returned unchanged (e.g. legacy public data).
        """
        out = []
        for r in results:
            meta = r.get("metadata", {})
            blob = meta.get("_enc")
            if blob:
                try:
                    _, decrypted_meta = self.decrypt_payload(blob)
                    r = {**r, "metadata": decrypted_meta}
                except ValueError:
                    # Wrong key or corrupted — return with redacted metadata
                    r = {**r, "metadata": {"_error": "decryption_failed"}}
            out.append(r)
        return out
