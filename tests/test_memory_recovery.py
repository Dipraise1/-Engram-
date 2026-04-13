"""
Memory layer — Multi-miner failure and recovery tests.

Tests the replication manager when multiple miners go offline simultaneously:
  - Atomic batch failure processing (no duplicate repair tasks)
  - Priority ordering: LOST before CRITICAL before DEGRADED
  - Fallback targeting when DHT-assigned peers are also offline
  - RepairTask fields and is_actionable flag
  - Full replication lifecycle: register → confirm → fail → recover
"""

from __future__ import annotations

import pytest

from engram.storage.dht import DHTRouter, Peer
from engram.storage.replication import (
    ReplicationManager,
    ReplicationStatus,
    RepairTask,
)
from engram.config import REPLICATION_FACTOR


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_peer(uid: int) -> Peer:
    return Peer(uid=uid, hotkey=f"5FhHotkey{uid:08d}xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")


def make_manager(n_peers: int = 20) -> ReplicationManager:
    local = make_peer(0)
    router = DHTRouter(local_peer=local)
    for i in range(1, n_peers + 1):
        router.add_peer(make_peer(i))
    return ReplicationManager(router=router)


def fake_cid(tag: str) -> str:
    digest = (tag * 64)[:64]
    return f"v1::{digest}"


CID_X = fake_cid("a")
CID_Y = fake_cid("b")
CID_Z = fake_cid("c")


# ── ReplicationRecord status transitions ─────────────────────────────────────

def test_fresh_record_is_lost() -> None:
    mgr = make_manager()
    rec = mgr.register(CID_X)
    assert rec.status == ReplicationStatus.LOST


def test_one_confirmed_is_critical() -> None:
    mgr = make_manager()
    rec = mgr.register(CID_X)
    mgr.confirm(CID_X, rec.assigned_uids[0])
    assert rec.status == ReplicationStatus.CRITICAL


def test_two_confirmed_is_degraded() -> None:
    mgr = make_manager()
    rec = mgr.register(CID_X)
    if REPLICATION_FACTOR > 2:
        mgr.confirm(CID_X, rec.assigned_uids[0])
        mgr.confirm(CID_X, rec.assigned_uids[1])
        assert rec.status == ReplicationStatus.DEGRADED


def test_all_confirmed_is_healthy() -> None:
    mgr = make_manager()
    rec = mgr.register(CID_X)
    for uid in rec.assigned_uids:
        mgr.confirm(CID_X, uid)
    assert rec.status == ReplicationStatus.HEALTHY
    assert not rec.needs_replication


# ── handle_miners_offline — single miner ─────────────────────────────────────

def test_single_miner_offline(capsys) -> None:
    mgr = make_manager()
    rec = mgr.register(CID_X)
    for uid in rec.assigned_uids:
        mgr.confirm(CID_X, uid)

    uid_to_drop = rec.confirmed_uids[0]
    tasks = mgr.handle_miners_offline([uid_to_drop])

    assert any(t.cid == CID_X for t in tasks)
    assert rec.replica_count == REPLICATION_FACTOR - 1


# ── handle_miners_offline — simultaneous failures ────────────────────────────

def test_two_miners_offline_deduplicated() -> None:
    """If two miners hold the same CID, that CID appears once in the repair plan."""
    mgr = make_manager()
    rec = mgr.register(CID_X)
    uid_a, uid_b = rec.assigned_uids[0], rec.assigned_uids[1]
    mgr.confirm(CID_X, uid_a)
    mgr.confirm(CID_X, uid_b)

    tasks = mgr.handle_miners_offline([uid_a, uid_b])

    cids_in_plan = [t.cid for t in tasks]
    assert cids_in_plan.count(CID_X) == 1, "CID must appear at most once in repair plan"


def test_three_miners_offline_across_cids() -> None:
    """Three miners hold different CIDs — all affected CIDs enter the repair plan."""
    mgr = make_manager(30)
    rec_x = mgr.register(CID_X)
    rec_y = mgr.register(CID_Y)
    rec_z = mgr.register(CID_Z)

    # Confirm one miner per CID (pick different miners if possible)
    uids = set()
    for rec, cid in [(rec_x, CID_X), (rec_y, CID_Y), (rec_z, CID_Z)]:
        uid = rec.assigned_uids[0]
        mgr.confirm(cid, uid)
        uids.add(uid)

    tasks = mgr.handle_miners_offline(list(uids))
    repaired_cids = {t.cid for t in tasks}
    # Every CID that lost a confirmed replica must appear
    assert CID_X in repaired_cids
    assert CID_Y in repaired_cids
    assert CID_Z in repaired_cids


def test_miners_offline_empty_list_returns_empty() -> None:
    mgr = make_manager()
    mgr.register(CID_X)
    tasks = mgr.handle_miners_offline([])
    assert tasks == []


def test_miners_offline_unconfirmed_uid_ignored() -> None:
    """A UID that was never confirmed should not affect the repair plan."""
    mgr = make_manager()
    rec = mgr.register(CID_X)
    for uid in rec.assigned_uids:
        mgr.confirm(CID_X, uid)

    before = rec.replica_count
    # Pass a UID that never confirmed anything
    mgr.handle_miners_offline([9999])
    assert rec.replica_count == before


# ── Priority ordering ─────────────────────────────────────────────────────────

def test_lost_before_critical_before_degraded() -> None:
    """LOST CIDs must appear before CRITICAL, which must appear before DEGRADED."""
    mgr = make_manager(30)

    # CID_X → LOST (0 confirmed)
    mgr.register(CID_X)

    # CID_Y → CRITICAL (1 confirmed)
    rec_y = mgr.register(CID_Y)
    mgr.confirm(CID_Y, rec_y.assigned_uids[0])

    # CID_Z → DEGRADED (2 confirmed, needs 3)
    if REPLICATION_FACTOR >= 3:
        rec_z = mgr.register(CID_Z)
        mgr.confirm(CID_Z, rec_z.assigned_uids[0])
        mgr.confirm(CID_Z, rec_z.assigned_uids[1])

    queue = mgr.prioritized_repair_queue()
    priorities = [t.priority for t in queue]
    # Priorities must be non-decreasing (lower = more urgent comes first)
    assert priorities == sorted(priorities)


def test_repair_task_status_matches_record() -> None:
    mgr = make_manager()
    rec = mgr.register(CID_X)
    mgr.confirm(CID_X, rec.assigned_uids[0])   # CRITICAL

    queue = mgr.prioritized_repair_queue()
    task = next(t for t in queue if t.cid == CID_X)
    assert task.status == ReplicationStatus.CRITICAL


def test_healthy_cids_not_in_queue() -> None:
    mgr = make_manager()
    rec = mgr.register(CID_X)
    for uid in rec.assigned_uids:
        mgr.confirm(CID_X, uid)

    queue = mgr.prioritized_repair_queue()
    assert not any(t.cid == CID_X for t in queue)


# ── RepairTask ────────────────────────────────────────────────────────────────

def test_repair_task_is_actionable_with_targets() -> None:
    mgr = make_manager(20)
    mgr.register(CID_X)   # LOST, needs all replicas

    tasks = mgr.prioritized_repair_queue()
    task = next(t for t in tasks if t.cid == CID_X)
    # With 20 online peers there should be actionable targets
    assert task.is_actionable


def test_repair_task_not_actionable_no_online_peers() -> None:
    """If no peers are online, repair task is still created but not actionable."""
    local = make_peer(0)
    router = DHTRouter(local_peer=local)
    # No peers added — empty routing table
    mgr = ReplicationManager(router=router)
    mgr.register(CID_X)

    tasks = mgr.prioritized_repair_queue()
    assert len(tasks) == 1
    assert not tasks[0].is_actionable


def test_repair_task_sorting() -> None:
    """RepairTask dataclass sorts by priority (lower = first)."""
    t_lost = RepairTask(priority=0, cid="a", status=ReplicationStatus.LOST)
    t_critical = RepairTask(priority=1, cid="b", status=ReplicationStatus.CRITICAL)
    t_degraded = RepairTask(priority=2, cid="c", status=ReplicationStatus.DEGRADED)

    tasks = sorted([t_degraded, t_lost, t_critical])
    assert tasks[0].status == ReplicationStatus.LOST
    assert tasks[1].status == ReplicationStatus.CRITICAL
    assert tasks[2].status == ReplicationStatus.DEGRADED


# ── Fallback targeting ────────────────────────────────────────────────────────

def test_fallback_to_non_assigned_peers() -> None:
    """
    When all DHT-assigned peers are offline, get_repair_targets must fall back
    to any remaining online peer rather than returning empty.
    """
    mgr = make_manager(10)
    rec = mgr.register(CID_X)

    # Simulate: DHT-assigned peers went offline too
    for uid in rec.assigned_uids:
        mgr._router.remove_peer(uid)

    # At least some other peers remain online
    remaining = mgr._router.all_peers()
    if not remaining:
        pytest.skip("All peers removed — cannot test fallback")

    targets = mgr.get_repair_targets(CID_X)
    assert len(targets) > 0


def test_no_duplicate_targets() -> None:
    """get_repair_targets must never return the same peer twice."""
    mgr = make_manager(20)
    rec = mgr.register(CID_X)
    mgr.confirm(CID_X, rec.assigned_uids[0])   # 1 confirmed

    targets = mgr.get_repair_targets(CID_X)
    uids = [p.uid for p in targets]
    assert len(uids) == len(set(uids)), "Duplicate repair targets"


def test_confirmed_peers_not_in_targets() -> None:
    """A peer that already holds the CID should never be a repair target."""
    mgr = make_manager(20)
    rec = mgr.register(CID_X)
    confirmed_uid = rec.assigned_uids[0]
    mgr.confirm(CID_X, confirmed_uid)

    targets = mgr.get_repair_targets(CID_X)
    assert all(p.uid != confirmed_uid for p in targets)


# ── Full lifecycle ────────────────────────────────────────────────────────────

def test_full_lifecycle_register_confirm_fail_recover() -> None:
    """
    End-to-end replication lifecycle:
    1. Register CID
    2. All replicas confirmed → HEALTHY
    3. Two miners simultaneously fail → DEGRADED/CRITICAL/LOST
    4. Repair plan returned → re-confirm on new miners → HEALTHY again
    """
    mgr = make_manager(20)
    rec = mgr.register(CID_X)

    # Confirm all replicas
    for uid in rec.assigned_uids:
        mgr.confirm(CID_X, uid)
    assert rec.status == ReplicationStatus.HEALTHY

    # Two miners go offline simultaneously
    failed = rec.confirmed_uids[:2]
    tasks = mgr.handle_miners_offline(failed)

    assert any(t.cid == CID_X for t in tasks)
    assert rec.status in (ReplicationStatus.CRITICAL, ReplicationStatus.DEGRADED)

    # Simulate successful repair: confirm on the suggested targets
    repair_task = next(t for t in tasks if t.cid == CID_X)
    for peer in repair_task.targets:
        mgr.confirm(CID_X, peer.uid)

    assert rec.status == ReplicationStatus.HEALTHY
