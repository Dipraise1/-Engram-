"""
Memory layer — Advanced vector store tests.

Tests beyond the basic CRUD in test_store.py:
  - Cosine similarity ranking (nearest neighbour correctness)
  - Upsert idempotency (same CID, updated vector)
  - Top-K boundary conditions
  - Persistence roundtrip (save → load → search)
  - Metadata round-trip
  - Delete then re-insert
  - Large batch upsert + search correctness
"""

from __future__ import annotations

import numpy as np
import pytest
import tempfile
from pathlib import Path

from engram.miner.store import FAISSStore, VectorRecord, SearchResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _v(*values: float) -> np.ndarray:
    return np.array(values, dtype=np.float32)


def _unit(values: list[float]) -> np.ndarray:
    a = np.array(values, dtype=np.float32)
    return a / np.linalg.norm(a)


def _record(cid: str, vec: np.ndarray, meta: dict | None = None) -> VectorRecord:
    return VectorRecord(cid=cid, embedding=vec, metadata=meta or {})


# ── Nearest-neighbour correctness ─────────────────────────────────────────────

def test_closest_vector_ranks_first() -> None:
    store = FAISSStore(dim=3)
    query = _unit([1.0, 0.0, 0.0])
    store.upsert(_record("close", _unit([0.99, 0.14, 0.0])))
    store.upsert(_record("far", _unit([0.0, 1.0, 0.0])))
    store.upsert(_record("opposite", _unit([-1.0, 0.0, 0.0])))

    results = store.search(query, top_k=3)
    assert results[0].cid == "close"


def test_scores_ascending_l2() -> None:
    # FAISSStore uses L2 distance: 0.0 = exact match, larger = less similar.
    # Results are returned most-similar-first (ascending L2 distance).
    store = FAISSStore(dim=3)
    for i in range(5):
        store.upsert(_record(f"cid{i}", _unit([float(i), 1.0, 0.0])))

    results = store.search(_unit([4.0, 1.0, 0.0]), top_k=5)
    scores = [r.score for r in results]
    assert scores == sorted(scores)  # ascending: smallest L2 distance first


def test_identical_vectors_same_score() -> None:
    store = FAISSStore(dim=4)
    v = _unit([1.0, 1.0, 0.0, 0.0])
    store.upsert(_record("a", v))
    store.upsert(_record("b", v.copy()))
    results = store.search(v, top_k=2)
    assert len(results) == 2
    assert abs(results[0].score - results[1].score) < 1e-5


# ── Upsert idempotency ────────────────────────────────────────────────────────

def test_upsert_same_cid_does_not_duplicate() -> None:
    store = FAISSStore(dim=3)
    v = _unit([1.0, 0.0, 0.0])
    store.upsert(_record("cid1", v))
    store.upsert(_record("cid1", v))   # second upsert of same CID
    assert store.count() == 1


def test_upsert_updates_vector() -> None:
    store = FAISSStore(dim=3)
    store.upsert(_record("cid1", _unit([1.0, 0.0, 0.0])))
    store.upsert(_record("cid1", _unit([0.0, 1.0, 0.0])))   # update to different vector

    # Searching near the new vector should return it; old position should score lower
    results = store.search(_unit([0.0, 1.0, 0.0]), top_k=1)
    assert results[0].cid == "cid1"


# ── Top-K boundaries ──────────────────────────────────────────────────────────

def test_top_k_larger_than_store_returns_all() -> None:
    store = FAISSStore(dim=3)
    for i in range(3):
        store.upsert(_record(f"cid{i}", _unit([float(i+1), 0.0, 0.0])))
    results = store.search(_unit([1.0, 0.0, 0.0]), top_k=100)
    assert len(results) == 3


def test_top_k_one_returns_one() -> None:
    store = FAISSStore(dim=3)
    for i in range(5):
        store.upsert(_record(f"cid{i}", _unit([float(i+1), 0.0, 0.0])))
    results = store.search(_unit([5.0, 0.0, 0.0]), top_k=1)
    assert len(results) == 1


def test_search_empty_store() -> None:
    store = FAISSStore(dim=3)
    results = store.search(_unit([1.0, 0.0, 0.0]))
    assert results == []


# ── Metadata round-trip ───────────────────────────────────────────────────────

def test_metadata_preserved() -> None:
    store = FAISSStore(dim=3)
    meta = {"source": "arxiv", "year": "2024", "model": "gpt-4"}
    store.upsert(_record("cid_meta", _unit([1.0, 0.0, 0.0]), meta=meta))

    rec = store.get("cid_meta")
    assert rec is not None
    assert rec.metadata["source"] == "arxiv"
    assert rec.metadata["year"] == "2024"
    assert rec.metadata["model"] == "gpt-4"


def test_metadata_in_search_results() -> None:
    store = FAISSStore(dim=3)
    store.upsert(_record("cid1", _unit([1.0, 0.0, 0.0]), meta={"tag": "alpha"}))
    results = store.search(_unit([1.0, 0.0, 0.0]), top_k=1)
    assert results[0].metadata.get("tag") == "alpha"


def test_empty_metadata_ok() -> None:
    store = FAISSStore(dim=3)
    store.upsert(_record("cid_empty", _unit([1.0, 0.0, 0.0]), meta={}))
    rec = store.get("cid_empty")
    assert rec is not None
    assert rec.metadata == {}


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_returns_true_for_existing() -> None:
    store = FAISSStore(dim=3)
    store.upsert(_record("cid1", _unit([1.0, 0.0, 0.0])))
    assert store.delete("cid1") is True


def test_delete_returns_false_for_missing() -> None:
    store = FAISSStore(dim=3)
    assert store.delete("nonexistent") is False


def test_delete_removes_from_search() -> None:
    store = FAISSStore(dim=3)
    v = _unit([1.0, 0.0, 0.0])
    store.upsert(_record("to_delete", v))
    store.upsert(_record("to_keep", _unit([0.9, 0.1, 0.0])))
    store.delete("to_delete")

    results = {r.cid for r in store.search(v, top_k=10)}
    assert "to_delete" not in results
    assert "to_keep" in results


def test_delete_then_reinsert() -> None:
    store = FAISSStore(dim=3)
    v = _unit([1.0, 0.0, 0.0])
    store.upsert(_record("cid1", v))
    store.delete("cid1")
    store.upsert(_record("cid1", v))

    assert store.count() == 1
    assert store.get("cid1") is not None


# ── Persistence roundtrip ─────────────────────────────────────────────────────

def test_save_and_load_roundtrip() -> None:
    # save(path) writes the FAISS index to `path` and metadata to `path.meta.json`
    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = str(Path(tmpdir) / "index.faiss")

        store1 = FAISSStore(dim=3)
        store1.upsert(_record("cid_persist", _unit([1.0, 0.0, 0.0]), meta={"k": "v"}))
        store1.save(index_path)

        store2 = FAISSStore(dim=3)
        store2.load(index_path)

        rec = store2.get("cid_persist")
        assert rec is not None
        assert rec.metadata.get("k") == "v"
        assert store2.count() == 1


def test_save_load_search_correctness() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = str(Path(tmpdir) / "index.faiss")

        store1 = FAISSStore(dim=4)
        query = _unit([1.0, 0.0, 0.0, 0.0])
        store1.upsert(_record("near", _unit([0.99, 0.1, 0.0, 0.0])))
        store1.upsert(_record("far", _unit([0.0, 1.0, 0.0, 0.0])))
        store1.save(index_path)

        store2 = FAISSStore(dim=4)
        store2.load(index_path)
        results = store2.search(query, top_k=1)
        assert results[0].cid == "near"


# ── Large batch ───────────────────────────────────────────────────────────────

def test_large_batch_upsert_and_search() -> None:
    """Insert 500 vectors and verify top-1 search returns the correct answer."""
    n = 500
    dim = 16
    store = FAISSStore(dim=dim)

    rng = np.random.default_rng(42)
    vecs = rng.standard_normal((n, dim)).astype(np.float32)
    # Normalise so cosine ≡ dot product
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs = vecs / norms

    for i in range(n):
        store.upsert(_record(f"cid_{i}", vecs[i]))

    assert store.count() == n

    # Query with an exact copy of record 42 — must be top-1
    results = store.search(vecs[42], top_k=5)
    assert results[0].cid == "cid_42"
    # L2 distance to itself should be ~0 (not a cosine-similarity score)
    assert results[0].score < 0.001
