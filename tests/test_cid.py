"""Tests for CID generation (Python fallback — Rust module tested via cargo test)."""

import numpy as np
import pytest

from engram.cid import generate_cid, parse_cid, verify_cid


def test_deterministic():
    emb = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    assert generate_cid(emb) == generate_cid(emb)


def test_different_embedding_different_cid():
    e1 = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    e2 = np.array([0.1, 0.2, 0.4], dtype=np.float32)
    assert generate_cid(e1) != generate_cid(e2)


def test_model_version_affects_cid():
    emb = np.array([0.5, 0.5], dtype=np.float32)
    assert generate_cid(emb, model_version="v1") != generate_cid(emb, model_version="v2")


def test_cid_format():
    emb = np.array([1.0], dtype=np.float32)
    cid = generate_cid(emb)
    assert cid.startswith("v1::")
    _, digest = cid.split("::", 1)
    assert len(digest) == 64


def test_verify_roundtrip():
    emb = np.array([0.9, 0.1, 0.5], dtype=np.float32)
    cid = generate_cid(emb)
    assert verify_cid(cid, emb)
    assert not verify_cid(cid, np.array([0.0], dtype=np.float32))


def test_parse_valid():
    emb = np.array([0.3], dtype=np.float32)
    cid = generate_cid(emb)
    version, digest = parse_cid(cid)
    assert version == "v1"
    assert len(digest) == 64


def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        parse_cid("notacid")
