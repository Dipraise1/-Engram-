"""Tests for DHT routing layer."""

import pytest
from engram.storage.dht import (
    DHTRouter,
    Peer,
    RoutingTable,
    cid_to_key,
    xor_distance,
)
from engram.config import REPLICATION_FACTOR


def make_peer(uid: int) -> Peer:
    return Peer(uid=uid, hotkey=f"hotkey_{uid:04d}")


def make_router(n_peers: int = 10) -> DHTRouter:
    local = make_peer(0)
    router = DHTRouter(local_peer=local)
    for i in range(1, n_peers + 1):
        router.add_peer(make_peer(i))
    return router


# ── XOR distance ──────────────────────────────────────────────────────────────

def test_xor_distance_zero():
    b = bytes(32)
    assert xor_distance(b, b) == 0


def test_xor_distance_nonzero():
    a = bytes([1] + [0] * 31)
    b = bytes([2] + [0] * 31)
    assert xor_distance(a, b) > 0


def test_xor_distance_symmetric():
    a = bytes(range(32))
    b = bytes(reversed(range(32)))
    assert xor_distance(a, b) == xor_distance(b, a)


# ── CID key ───────────────────────────────────────────────────────────────────

def test_cid_to_key_length():
    key = cid_to_key("v1::abcdef1234")
    assert len(key) == 32


def test_cid_to_key_deterministic():
    assert cid_to_key("v1::abc") == cid_to_key("v1::abc")


def test_cid_to_key_different():
    assert cid_to_key("v1::abc") != cid_to_key("v1::xyz")


# ── Routing table ─────────────────────────────────────────────────────────────

def test_routing_table_add():
    local = make_peer(0)
    table = RoutingTable(local_id=local.node_id)
    table.add(make_peer(1))
    assert table.size() == 1


def test_routing_table_no_self():
    local = make_peer(0)
    table = RoutingTable(local_id=local.node_id)
    table.add(local)
    assert table.size() == 0


def test_routing_table_closest_returns_k():
    local = make_peer(0)
    table = RoutingTable(local_id=local.node_id)
    for i in range(1, 20):
        table.add(make_peer(i))
    key = cid_to_key("v1::testkey")
    results = table.closest(key, k=5)
    assert len(results) == 5


def test_routing_table_dedup():
    local = make_peer(0)
    table = RoutingTable(local_id=local.node_id)
    p = make_peer(1)
    table.add(p)
    table.add(p)
    assert table.size() == 1


# ── DHT Router ────────────────────────────────────────────────────────────────

def test_assign_returns_replication_factor():
    router = make_router(10)
    peers = router.assign("v1::somecid")
    assert len(peers) == REPLICATION_FACTOR


def test_assign_deterministic():
    router = make_router(10)
    a = router.assign("v1::somecid")
    b = router.assign("v1::somecid")
    assert [p.uid for p in a] == [p.uid for p in b]


def test_assign_different_cids_different_peers():
    router = make_router(20)
    a = router.assign("v1::aaaaaa")
    b = router.assign("v1::zzzzzz")
    # With enough peers, different CIDs should map to different sets
    assert [p.uid for p in a] != [p.uid for p in b]


def test_lookup_returns_peers():
    router = make_router(10)
    peers = router.lookup("v1::somecid")
    assert len(peers) > 0


def test_should_store_local_peer():
    # With enough peers, the local node should be assigned to some CIDs
    # Use a larger peer set so XOR space is well populated
    router = make_router(20)
    results = [router.should_store(f"v1::cid{i:04d}") for i in range(200)]
    assert any(results)


def test_peer_count():
    router = make_router(5)
    assert router.peer_count() == 5


def test_remove_peer():
    router = make_router(5)
    router.remove_peer(1)
    assert router.peer_count() == 4
