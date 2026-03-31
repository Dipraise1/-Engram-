"""Tests for FAISSStore (no external dependencies needed)."""

import numpy as np
import pytest

from engram.miner.store import FAISSStore, VectorRecord


@pytest.fixture
def store():
    return FAISSStore(dim=4)


def make_record(cid: str, vec: list[float]) -> VectorRecord:
    return VectorRecord(
        cid=cid,
        embedding=np.array(vec, dtype=np.float32),
        metadata={"source": "test"},
    )


def test_upsert_and_count(store):
    store.upsert(make_record("cid1", [1.0, 0.0, 0.0, 0.0]))
    assert store.count() == 1


def test_search_returns_results(store):
    store.upsert(make_record("cid1", [1.0, 0.0, 0.0, 0.0]))
    store.upsert(make_record("cid2", [0.0, 1.0, 0.0, 0.0]))
    results = store.search(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32), top_k=2)
    assert len(results) > 0
    assert results[0].cid == "cid1"


def test_get_existing(store):
    store.upsert(make_record("cid1", [1.0, 0.0, 0.0, 0.0]))
    record = store.get("cid1")
    assert record is not None
    assert record.cid == "cid1"


def test_get_missing(store):
    assert store.get("nonexistent") is None


def test_delete(store):
    store.upsert(make_record("cid1", [1.0, 0.0, 0.0, 0.0]))
    assert store.delete("cid1")
    assert store.get("cid1") is None


def test_search_empty(store):
    results = store.search(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32))
    assert results == []
