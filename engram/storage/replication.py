"""
Engram — Replication Layer

Ensures each embedding is stored on REPLICATION_FACTOR miners.

Phase 1: Simple 3× replication (store on 3 closest peers by XOR distance)
Phase 2: Erasure coding (planned — splits vector into N shards, any k recover)

Responsibilities:
  - On ingest: push a vector to all assigned miners
  - On miner failure: detect under-replication and re-replicate
  - Track replication health per CID

Multi-miner failure handling:
  - handle_miners_offline(uids) processes all failures atomically in a single
    pass, deduplicates affected CIDs, and returns a priority-ordered repair plan
  - LOST and CRITICAL CIDs are scheduled before DEGRADED ones
  - get_repair_targets falls back to any online peer if the DHT-assigned peers
    are themselves offline (avoids silent data loss during coordinated failures)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from loguru import logger

from engram.config import REPLICATION_FACTOR
from engram.storage.dht import DHTRouter, Peer


# ── Types ─────────────────────────────────────────────────────────────────────

class ReplicationStatus(str, Enum):
    HEALTHY   = "healthy"    # stored on >= REPLICATION_FACTOR miners
    DEGRADED  = "degraded"   # stored on 1 < n < REPLICATION_FACTOR miners
    CRITICAL  = "critical"   # stored on exactly 1 miner
    LOST      = "lost"       # no known replicas


# Priority values: lower number = more urgent.
_STATUS_PRIORITY: dict[ReplicationStatus, int] = {
    ReplicationStatus.LOST:     0,
    ReplicationStatus.CRITICAL: 1,
    ReplicationStatus.DEGRADED: 2,
}


@dataclass
class ReplicationRecord:
    cid: str
    assigned_uids: list[int]          # miners that should hold this CID
    confirmed_uids: list[int] = field(default_factory=list)  # miners that proved they hold it
    created_at: float = field(default_factory=time.time)
    last_checked: float = 0.0

    @property
    def replica_count(self) -> int:
        return len(self.confirmed_uids)

    @property
    def status(self) -> ReplicationStatus:
        n = self.replica_count
        if n >= REPLICATION_FACTOR:
            return ReplicationStatus.HEALTHY
        if n == 1:
            return ReplicationStatus.CRITICAL
        if n == 0:
            return ReplicationStatus.LOST
        return ReplicationStatus.DEGRADED

    @property
    def needs_replication(self) -> bool:
        return self.replica_count < REPLICATION_FACTOR


@dataclass(order=True)
class RepairTask:
    """
    A single unit of repair work, sortable by urgency.

    Fields are ordered so that dataclass comparison gives LOST < CRITICAL < DEGRADED,
    which means `sorted(tasks)` produces the highest-urgency work first.
    """
    priority: int                              # 0=LOST, 1=CRITICAL, 2=DEGRADED
    cid: str               = field(compare=False)
    status: ReplicationStatus = field(compare=False)
    targets: list[Peer]    = field(compare=False, default_factory=list)

    @property
    def is_actionable(self) -> bool:
        """True if there are online peers that can receive the repair copy."""
        return len(self.targets) > 0


# ── Replication Manager ───────────────────────────────────────────────────────

class ReplicationManager:
    """
    Tracks replication state for all stored CIDs and drives re-replication
    when miners go offline or fail storage proofs.
    """

    def __init__(self, router: DHTRouter) -> None:
        self._router = router
        self._records: dict[str, ReplicationRecord] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, cid: str) -> ReplicationRecord:
        """
        Register a new CID for replication tracking.
        Called immediately after ingest.
        """
        assigned = self._router.assign(cid, replication=REPLICATION_FACTOR)
        record = ReplicationRecord(
            cid=cid,
            assigned_uids=[p.uid for p in assigned],
        )
        self._records[cid] = record
        logger.debug(f"Replication registered | cid={cid[:16]}... | assigned={record.assigned_uids}")
        return record

    def confirm(self, cid: str, uid: int) -> None:
        """Mark a miner as confirmed to hold a CID (after successful storage proof)."""
        record = self._records.get(cid)
        if record and uid not in record.confirmed_uids:
            record.confirmed_uids.append(uid)
            record.last_checked = time.time()

    def unconfirm(self, cid: str, uid: int) -> None:
        """Remove a miner from confirmed holders (failed proof or went offline)."""
        record = self._records.get(cid)
        if record and uid in record.confirmed_uids:
            record.confirmed_uids.remove(uid)
            logger.warning(
                f"Replica lost | cid={cid[:16]}... | uid={uid} | "
                f"remaining={record.replica_count}"
            )

    # ── Health ────────────────────────────────────────────────────────────────

    def get_status(self, cid: str) -> ReplicationStatus | None:
        record = self._records.get(cid)
        return record.status if record else None

    def under_replicated(self) -> list[ReplicationRecord]:
        """Return all CIDs that need more replicas."""
        return [r for r in self._records.values() if r.needs_replication]

    def health_summary(self) -> dict[str, int]:
        """Count CIDs by replication status."""
        counts: dict[str, int] = {s.value: 0 for s in ReplicationStatus}
        for record in self._records.values():
            counts[record.status.value] += 1
        return counts

    # ── Re-replication ────────────────────────────────────────────────────────

    def get_repair_targets(self, cid: str) -> list[Peer]:
        """
        Return peers that should receive a repair copy of a CID.

        Strategy:
          1. Prefer DHT-assigned peers that are online but not yet confirmed.
          2. If the assigned set doesn't have enough online peers (e.g., they
             also went offline), fall back to any other online peer.
             This prevents silent data loss when a coordinated failure takes out
             both the original holders AND their DHT-assigned replacements.
        """
        record = self._records.get(cid)
        if not record:
            return []

        needed = REPLICATION_FACTOR - record.replica_count
        if needed <= 0:
            return []

        online_peers = self._router.all_peers()
        online_uids = {p.uid for p in online_peers}
        confirmed = set(record.confirmed_uids)

        # Stage 1: DHT-assigned peers that are online and not yet confirmed
        assigned = self._router.assign(cid, replication=REPLICATION_FACTOR * 2)
        assigned_uids = {p.uid for p in assigned}
        candidates: list[Peer] = [
            p for p in assigned
            if p.uid not in confirmed and p.uid in online_uids
        ]

        # Stage 2: fallback to any online peer not already holding the CID
        if len(candidates) < needed:
            fallback = [
                p for p in online_peers
                if p.uid not in confirmed and p.uid not in assigned_uids
            ]
            candidates.extend(fallback)

        return candidates[:needed]

    def handle_miner_offline(self, uid: int) -> list[str]:
        """
        Called when a single miner goes offline.
        Returns CIDs that are now under-replicated and need repair.

        For simultaneous multi-miner failures, prefer handle_miners_offline()
        which processes all UIDs atomically to avoid duplicate repair work.
        """
        affected = []
        for cid, record in self._records.items():
            if uid in record.confirmed_uids:
                self.unconfirm(cid, uid)
                if record.needs_replication:
                    affected.append(cid)

        if affected:
            logger.warning(
                f"Miner uid={uid} offline | {len(affected)} CIDs need re-replication"
            )
        return affected

    def handle_miners_offline(self, uids: Iterable[int]) -> list[RepairTask]:
        """
        Handle multiple miners going offline simultaneously.

        Processes all UIDs in a single pass over the record set so that:
          - Each CID appears in the output at most once (no duplicate repair tasks)
          - The status used for prioritisation reflects ALL losses, not just the
            first one processed (avoids underestimating severity)
          - Returns a priority-ordered repair plan: LOST → CRITICAL → DEGRADED

        Args:
            uids: UIDs of miners that have gone offline.

        Returns:
            Sorted list of RepairTask, highest-urgency first.
        """
        uid_set = set(uids)
        if not uid_set:
            return []

        affected_cids: set[str] = set()

        for cid, record in self._records.items():
            # Find which of the offline UIDs were confirmed holders of this CID
            offline_confirmed = uid_set & set(record.confirmed_uids)
            if not offline_confirmed:
                continue

            # Remove them all in one go
            for uid in offline_confirmed:
                record.confirmed_uids.remove(uid)
                logger.warning(
                    f"Replica lost | cid={cid[:16]}... | uid={uid} | "
                    f"remaining={record.replica_count}"
                )

            if record.needs_replication:
                affected_cids.add(cid)

        if affected_cids:
            logger.warning(
                f"{len(uid_set)} miners offline | "
                f"{len(affected_cids)} CIDs need re-replication"
            )

        return self._build_repair_tasks(affected_cids)

    def prioritized_repair_queue(self, cids: set[str] | None = None) -> list[RepairTask]:
        """
        Build a priority-ordered repair plan for under-replicated CIDs.

        Args:
            cids: restrict to this subset of CIDs (default: all under-replicated)

        Returns:
            RepairTask list sorted by urgency: LOST first, then CRITICAL, then DEGRADED.
            Tasks where no online peer is available (is_actionable=False) are still
            included so the caller can log them and retry later.
        """
        source_cids = cids if cids is not None else {
            cid for cid, rec in self._records.items() if rec.needs_replication
        }
        return self._build_repair_tasks(source_cids)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_repair_tasks(self, cids: set[str]) -> list[RepairTask]:
        """Build and sort RepairTask objects for a set of CIDs."""
        tasks: list[RepairTask] = []
        for cid in cids:
            record = self._records.get(cid)
            if record is None or not record.needs_replication:
                continue
            status = record.status
            priority = _STATUS_PRIORITY.get(status, 9)
            targets = self.get_repair_targets(cid)
            tasks.append(RepairTask(
                priority=priority,
                cid=cid,
                status=status,
                targets=targets,
            ))
        tasks.sort()
        return tasks

    def total_cids(self) -> int:
        return len(self._records)

    def get_record(self, cid: str) -> ReplicationRecord | None:
        return self._records.get(cid)
