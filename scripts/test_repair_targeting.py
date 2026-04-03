"""
Phase 2.5 — Repair Targeting Test

Verifies that:
1. Validator detects DEGRADED replication when a miner goes offline
2. handle_miner_offline() marks affected CIDs under-replicated
3. get_repair_targets() returns the correct peers to repair to
4. Miner going offline → validator can route repair to a live miner

This is a unit-level integration test — it does NOT require a running local chain.
It builds DHT + ReplicationManager objects directly, simulates offline events,
and checks the repair logic end-to-end.

Run:
  python scripts/test_repair_targeting.py
"""

import sys
sys.path.insert(0, ".")

import numpy as np
from engram.cid import generate_cid
from engram.storage.dht import DHTRouter, Peer
from engram.storage.replication import ReplicationManager, ReplicationStatus
from engram.config import REPLICATION_FACTOR

PASS = "✓"
FAIL = "✗"
results = []


def check(label: str, condition: bool) -> None:
    status = PASS if condition else FAIL
    print(f"  {status}  {label}")
    results.append((label, condition))


def main() -> None:
    print("=" * 60)
    print("Phase 2.5 — Repair Targeting Test")
    print(f"  REPLICATION_FACTOR = {REPLICATION_FACTOR}")
    print("=" * 60)

    # ── Setup: 4 miners + 1 validator ────────────────────────────────────────
    validator_peer = Peer(uid=99, hotkey="validator_hotkey_aaaaaa")
    miner_peers = [
        Peer(uid=0, hotkey="miner0_hotkey_111111"),
        Peer(uid=1, hotkey="miner1_hotkey_222222"),
        Peer(uid=2, hotkey="miner2_hotkey_333333"),
        Peer(uid=3, hotkey="miner3_hotkey_444444"),
    ]

    router = DHTRouter(local_peer=validator_peer)
    for p in miner_peers:
        router.add_peer(p)

    replication_mgr = ReplicationManager(router=router)

    # ── Generate 5 test CIDs ──────────────────────────────────────────────────
    rng = np.random.RandomState(7)
    cids = []
    for i in range(5):
        emb = rng.randn(384).astype(np.float32)
        emb = emb / np.linalg.norm(emb)
        cid = generate_cid(emb, metadata={"test_id": i})
        cids.append(cid)

    print(f"\n[1] Register {len(cids)} CIDs for replication tracking")
    for cid in cids:
        record = replication_mgr.register(cid)
        print(f"    CID {cid[:20]}… → assigned UIDs: {record.assigned_uids}")

    check("All CIDs registered", replication_mgr.total_cids() == len(cids))

    # ── Simulate: all assigned miners confirm storage ─────────────────────────
    print("\n[2] Simulate storage proofs — all assigned miners confirm")
    for cid in cids:
        record = replication_mgr.get_record(cid)
        for uid in record.assigned_uids:
            replication_mgr.confirm(cid, uid)

    all_healthy = all(
        replication_mgr.get_status(cid) == ReplicationStatus.HEALTHY
        for cid in cids
    )
    check(f"All CIDs HEALTHY (confirmed ≥ {REPLICATION_FACTOR} replicas)", all_healthy)

    summary = replication_mgr.health_summary()
    print(f"    Health summary: {summary}")

    # ── Find which CIDs are assigned to uid=1 ────────────────────────────────
    print("\n[3] Take uid=1 offline — detect affected CIDs")
    affected_cids = replication_mgr.handle_miner_offline(uid=1)
    print(f"    Affected CIDs (need repair): {len(affected_cids)}")
    for cid in affected_cids:
        record = replication_mgr.get_record(cid)
        print(f"      CID {cid[:20]}… | replicas={record.replica_count} | status={record.status.value}")

    # With 4 miners and RF=3, uid=1 may be assigned to some CIDs.
    # After going offline, those CIDs drop to 2 replicas → DEGRADED.
    cids_assigned_to_1 = [
        cid for cid in cids
        if 1 in replication_mgr.get_record(cid).assigned_uids
    ]
    check(
        f"handle_miner_offline returns exactly the CIDs assigned to uid=1 ({len(cids_assigned_to_1)})",
        set(affected_cids) == set(cids_assigned_to_1),
    )

    degraded = [cid for cid in cids if replication_mgr.get_status(cid) == ReplicationStatus.DEGRADED]
    check("Affected CIDs are DEGRADED (not HEALTHY)", set(degraded) == set(affected_cids))

    # ── Repair targeting: find which peer should receive repair copies ─────────
    print("\n[4] Compute repair targets for degraded CIDs")
    # Remove uid=1 from routing table to simulate it being offline
    router.remove_peer(uid=1)

    repair_targets_found = True
    for cid in affected_cids:
        targets = replication_mgr.get_repair_targets(cid)
        target_uids = [p.uid for p in targets]
        print(f"    CID {cid[:20]}… → repair to UIDs: {target_uids}")
        if not targets:
            repair_targets_found = False

    check("Repair targets identified for all degraded CIDs", repair_targets_found)

    # Verify repair targets don't include the offline miner
    no_offline_in_targets = all(
        1 not in [p.uid for p in replication_mgr.get_repair_targets(cid)]
        for cid in affected_cids
    )
    check("Repair targets exclude the offline miner (uid=1)", no_offline_in_targets)

    # ── Simulate repair completed ─────────────────────────────────────────────
    print("\n[5] Simulate repair: confirm replacement replicas")
    for cid in affected_cids:
        targets = replication_mgr.get_repair_targets(cid)
        for peer in targets:
            replication_mgr.confirm(cid, peer.uid)

    all_healthy_again = all(
        replication_mgr.get_status(cid) == ReplicationStatus.HEALTHY
        for cid in cids
    )
    check("All CIDs HEALTHY again after repair", all_healthy_again)

    summary_after = replication_mgr.health_summary()
    print(f"    Health summary after repair: {summary_after}")

    # ── under_replicated() helper ─────────────────────────────────────────────
    print("\n[6] under_replicated() returns empty after repair")
    under = replication_mgr.under_replicated()
    check("under_replicated() returns [] after full repair", len(under) == 0)

    # ── Final summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for label, ok in results:
        print(f"  {'✓' if ok else '✗'}  {label}")
    print(f"\n  {passed}/{total} checks passed")
    print(f"\n  Overall: {'PASS ✓' if passed == total else 'FAIL ✗'}")

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
