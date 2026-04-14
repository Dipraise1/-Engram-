"""Tests for replication manager."""

import pytest
from pathlib import Path
from engram.storage.dht import DHTRouter, Peer
from engram.storage.replication import ReplicationManager, ReplicationStatus
from engram.config import REPLICATION_FACTOR


def make_peer(uid: int) -> Peer:
    return Peer(uid=uid, hotkey=f"hotkey_{uid:04d}")


def make_manager(n_peers: int = 10) -> ReplicationManager:
    local = make_peer(0)
    router = DHTRouter(local_peer=local)
    for i in range(1, n_peers + 1):
        router.add_peer(make_peer(i))
    return ReplicationManager(router=router, db_path=Path(":memory:"))


TEST_CID = "v1::abc123def456abc123def456abc123def456abc123def456abc123def456abc1"


def test_register_creates_record():
    mgr = make_manager()
    record = mgr.register(TEST_CID)
    assert record.cid == TEST_CID
    assert len(record.assigned_uids) == REPLICATION_FACTOR


def test_initial_status_lost():
    mgr = make_manager()
    record = mgr.register(TEST_CID)
    assert record.status == ReplicationStatus.LOST


def test_confirm_updates_status():
    mgr = make_manager()
    record = mgr.register(TEST_CID)
    uid = record.assigned_uids[0]
    mgr.confirm(TEST_CID, uid)
    assert record.replica_count == 1
    assert record.status == ReplicationStatus.CRITICAL


def test_fully_replicated_is_healthy():
    mgr = make_manager()
    record = mgr.register(TEST_CID)
    for uid in record.assigned_uids[:REPLICATION_FACTOR]:
        mgr.confirm(TEST_CID, uid)
    assert record.status == ReplicationStatus.HEALTHY
    assert not record.needs_replication


def test_unconfirm_reduces_count():
    mgr = make_manager()
    record = mgr.register(TEST_CID)
    uid = record.assigned_uids[0]
    mgr.confirm(TEST_CID, uid)
    mgr.unconfirm(TEST_CID, uid)
    assert record.replica_count == 0


def test_miner_offline_returns_affected_cids():
    mgr = make_manager()
    record = mgr.register(TEST_CID)
    uid = record.assigned_uids[0]
    mgr.confirm(TEST_CID, uid)
    affected = mgr.handle_miner_offline(uid)
    assert TEST_CID in affected


def test_health_summary_keys():
    mgr = make_manager()
    mgr.register(TEST_CID)
    summary = mgr.health_summary()
    assert "healthy" in summary
    assert "degraded" in summary
    assert "lost" in summary


def test_total_cids():
    mgr = make_manager()
    mgr.register(TEST_CID)
    mgr.register("v1::" + "b" * 64)
    assert mgr.total_cids() == 2


def test_get_repair_targets():
    mgr = make_manager(10)
    record = mgr.register(TEST_CID)
    # Confirm only one replica
    mgr.confirm(TEST_CID, record.assigned_uids[0])
    targets = mgr.get_repair_targets(TEST_CID)
    assert len(targets) > 0
