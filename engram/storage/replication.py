"""
Engram — Replication Layer

Ensures each embedding is stored on REPLICATION_FACTOR miners.

Phase 1: Simple 3× replication (store on 3 closest peers by XOR distance)
Phase 2: Erasure coding (planned — splits vector into N shards, any k recover)

Responsibilities:
  - On ingest: push a vector to all assigned miners
  - On miner failure: detect under-replication and re-replicate
  - Track replication health per CID
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger

from engram.config import REPLICATION_FACTOR
from engram.storage.dht import DHTRouter, Peer


# ── Types ─────────────────────────────────────────────────────────────────────

class ReplicationStatus(str, Enum):
    HEALTHY   = "healthy"    # stored on >= REPLICATION_FACTOR miners
    DEGRADED  = "degraded"   # stored on 1 < n < REPLICATION_FACTOR miners
    CRITICAL  = "critical"   # stored on 1 miner only
    LOST      = "lost"       # no known replicas


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

        Called when a CID is under-replicated. Returns peers that are:
          1. In the assigned set for this CID
          2. Not already confirmed holders
          3. Currently online (in routing table)
        """
        record = self._records.get(cid)
        if not record:
            return []

        online_uids = {p.uid for p in self._router.all_peers()}
        confirmed = set(record.confirmed_uids)

        # Prefer assigned miners first, then any online peer
        assigned = self._router.assign(cid, replication=REPLICATION_FACTOR * 2)
        candidates = [
            p for p in assigned
            if p.uid not in confirmed and p.uid in online_uids
        ]

        needed = REPLICATION_FACTOR - record.replica_count
        return candidates[:needed]

    def handle_miner_offline(self, uid: int) -> list[str]:
        """
        Called when a miner goes offline.
        Returns CIDs that are now under-replicated and need repair.
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

    def total_cids(self) -> int:
        return len(self._records)

    def get_record(self, cid: str) -> ReplicationRecord | None:
        return self._records.get(cid)
