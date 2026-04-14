"""
Tests for HybridEncryption (X25519 + HKDF + AES-256-GCM).

Covers:
  - Keypair generation
  - Round-trip encrypt/decrypt
  - Forward secrecy: each message gets a unique ephemeral key
  - Write-only client (public key only) can encrypt but not decrypt
  - Wrong private key cannot decrypt
  - Tampered ciphertext rejected (GCM auth tag)
  - Backward compat: NamespaceEncryption still works
  - EngramClient accepts HybridEncryption instance
  - decrypt_results works for both schemes
"""

from __future__ import annotations

import base64
import pytest

from engram.sdk.encryption import (
    HybridEncryption,
    NamespaceEncryption,
    generate_keypair,
    public_key_from_private,
)


# ── Key generation ────────────────────────────────────────────────────────────

def test_generate_keypair_lengths():
    priv, pub = generate_keypair()
    assert len(priv) == 32
    assert len(pub)  == 32

def test_generate_keypair_unique():
    k1 = generate_keypair()
    k2 = generate_keypair()
    assert k1[0] != k2[0]
    assert k1[1] != k2[1]

def test_public_key_from_private():
    priv, pub = generate_keypair()
    assert public_key_from_private(priv) == pub

def test_keypair_requires_at_least_one_key():
    with pytest.raises(ValueError):
        HybridEncryption()


# ── Round-trip ────────────────────────────────────────────────────────────────

def test_roundtrip_text_and_metadata():
    priv, pub = generate_keypair()
    enc = HybridEncryption(private_key=priv)
    blob = enc.encrypt_payload("The transformer architecture changed everything.", {"source": "arxiv"})
    text, meta = enc.decrypt_payload(blob)
    assert text == "The transformer architecture changed everything."
    assert meta == {"source": "arxiv"}

def test_roundtrip_empty_text():
    priv, _ = generate_keypair()
    enc = HybridEncryption(private_key=priv)
    blob = enc.encrypt_payload(None, {"key": "value"})
    text, meta = enc.decrypt_payload(blob)
    assert text == ""
    assert meta == {"key": "value"}

def test_roundtrip_empty_metadata():
    priv, _ = generate_keypair()
    enc = HybridEncryption(private_key=priv)
    blob = enc.encrypt_payload("hello", {})
    text, meta = enc.decrypt_payload(blob)
    assert text == "hello"
    assert meta == {}

def test_roundtrip_unicode():
    priv, _ = generate_keypair()
    enc = HybridEncryption(private_key=priv)
    text_in = "こんにちは世界 🌍"
    blob = enc.encrypt_payload(text_in, {})
    text, _ = enc.decrypt_payload(blob)
    assert text == text_in


# ── Forward secrecy ───────────────────────────────────────────────────────────

def test_same_plaintext_produces_different_blobs():
    """Each call generates a fresh ephemeral keypair — no two blobs are alike."""
    priv, _ = generate_keypair()
    enc = HybridEncryption(private_key=priv)
    blob1 = enc.encrypt_payload("same text", {})
    blob2 = enc.encrypt_payload("same text", {})
    assert blob1 != blob2

def test_different_ephemeral_keys_per_message():
    """First 32 bytes of decoded wire = ephemeral public key. Must differ."""
    priv, _ = generate_keypair()
    enc = HybridEncryption(private_key=priv)
    raw1 = base64.urlsafe_b64decode(enc.encrypt_payload("msg", {}))
    raw2 = base64.urlsafe_b64decode(enc.encrypt_payload("msg", {}))
    assert raw1[:32] != raw2[:32]


# ── Write-only client ─────────────────────────────────────────────────────────

def test_public_key_only_can_encrypt():
    priv, pub = generate_keypair()
    writer = HybridEncryption(public_key=pub)
    blob = writer.encrypt_payload("write-only test", {"tag": "secret"})
    assert blob  # produced without error

def test_public_key_only_cannot_decrypt():
    _, pub = generate_keypair()
    writer = HybridEncryption(public_key=pub)
    blob = writer.encrypt_payload("write-only test", {})
    with pytest.raises(ValueError, match="no private key"):
        writer.decrypt_payload(blob)

def test_writer_encrypted_readable_by_owner():
    priv, pub = generate_keypair()
    writer = HybridEncryption(public_key=pub)
    owner  = HybridEncryption(private_key=priv)
    blob = writer.encrypt_payload("secret from writer", {"ts": "2026"})
    text, meta = owner.decrypt_payload(blob)
    assert text == "secret from writer"
    assert meta == {"ts": "2026"}


# ── Wrong key rejection ───────────────────────────────────────────────────────

def test_wrong_private_key_rejected():
    priv1, _ = generate_keypair()
    priv2, _ = generate_keypair()
    enc1 = HybridEncryption(private_key=priv1)
    enc2 = HybridEncryption(private_key=priv2)
    blob = enc1.encrypt_payload("secret", {})
    with pytest.raises(ValueError):
        enc2.decrypt_payload(blob)


# ── Tamper detection ──────────────────────────────────────────────────────────

def test_tampered_ciphertext_rejected():
    priv, _ = generate_keypair()
    enc = HybridEncryption(private_key=priv)
    blob = enc.encrypt_payload("untampered", {})
    raw = bytearray(base64.urlsafe_b64decode(blob))
    raw[-1] ^= 0xFF   # flip last byte of auth tag
    tampered = base64.urlsafe_b64encode(bytes(raw)).decode()
    with pytest.raises(ValueError):
        enc.decrypt_payload(tampered)

def test_truncated_blob_rejected():
    priv, _ = generate_keypair()
    enc = HybridEncryption(private_key=priv)
    blob = enc.encrypt_payload("text", {})
    truncated = blob[:20]
    with pytest.raises(ValueError):
        enc.decrypt_payload(truncated)


# ── decrypt_results ───────────────────────────────────────────────────────────

def test_decrypt_results_hybrid():
    priv, pub = generate_keypair()
    writer = HybridEncryption(public_key=pub)
    owner  = HybridEncryption(private_key=priv)

    blob = writer.encrypt_payload("doc text", {"title": "My Doc"})
    results = [
        {"cid": "v1::abc", "score": 0.9, "metadata": {"_enc": blob}},
        {"cid": "v1::def", "score": 0.8, "metadata": {"plain": "no encryption"}},
    ]
    decrypted = owner.decrypt_results(results)
    assert decrypted[0]["metadata"] == {"title": "My Doc"}
    assert decrypted[1]["metadata"] == {"plain": "no encryption"}

def test_decrypt_results_wrong_key_returns_error():
    priv1, pub1 = generate_keypair()
    priv2, _    = generate_keypair()
    blob = HybridEncryption(public_key=pub1).encrypt_payload("text", {})
    results = [{"cid": "v1::abc", "score": 0.9, "metadata": {"_enc": blob}}]
    decrypted = HybridEncryption(private_key=priv2).decrypt_results(results)
    assert decrypted[0]["metadata"] == {"_error": "decryption_failed"}


# ── Backward compat: NamespaceEncryption still works ─────────────────────────

def test_namespace_encryption_roundtrip():
    enc = NamespaceEncryption("my-ns", "super-secret-key-16chars")
    blob = enc.encrypt_payload("legacy text", {"v": "1"})
    text, meta = enc.decrypt_payload(blob)
    assert text == "legacy text"
    assert meta == {"v": "1"}

def test_namespace_encryption_wrong_key_rejected():
    enc1 = NamespaceEncryption("ns", "correct-key-16chars-here")
    enc2 = NamespaceEncryption("ns", "wrong-key-16chars-xxxxx!")
    blob = enc1.encrypt_payload("secret", {})
    with pytest.raises(ValueError):
        enc2.decrypt_payload(blob)


# ── EngramClient accepts HybridEncryption ────────────────────────────────────

def test_engram_client_accepts_hybrid_encryption():
    from engram.sdk.client import EngramClient
    priv, _ = generate_keypair()
    enc = HybridEncryption(private_key=priv)
    client = EngramClient(
        miner_url="http://localhost:8091",
        namespace="test-ns",
        encryption=enc,
    )
    assert client._enc is enc

def test_engram_client_hybrid_takes_priority_over_password():
    from engram.sdk.client import EngramClient
    priv, _ = generate_keypair()
    enc = HybridEncryption(private_key=priv)
    client = EngramClient(
        miner_url="http://localhost:8091",
        namespace="test-ns",
        namespace_key="should-be-ignored",
        encryption=enc,
    )
    assert isinstance(client._enc, HybridEncryption)

def test_engram_client_falls_back_to_namespace_encryption():
    from engram.sdk.client import EngramClient
    client = EngramClient(
        miner_url="http://localhost:8091",
        namespace="test-ns",
        namespace_key="my-secret-key-16chars",
    )
    assert isinstance(client._enc, NamespaceEncryption)
