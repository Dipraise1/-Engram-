"""
Memory layer — End-to-end lifecycle tests.

Tests the full memory layer stack without any miner/validator network machinery:

  1. Ingest: embed text → generate CID → store vector
  2. Search: query by vector → verify nearest-neighbour results
  3. Prove: validator challenges → miner responds → validator verifies
  4. Replicate: assign to peers, confirm, handle failures, recover
  5. Namespace: same lifecycle with a private namespace

These tests use FAISSStore (no Qdrant) and mock embeddings so they run
in CI with zero external services.
"""

from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import patch

from engram.miner.store import FAISSStore, VectorRecord
from engram.storage.dht import DHTRouter, Peer
from engram.storage.replication import ReplicationManager, ReplicationStatus
from engram.config import REPLICATION_FACTOR

try:
    import engram_core
    _RUST = True
except ImportError:
    _RUST = False

_BATCH = _RUST and hasattr(engram_core, "generate_batch_challenge")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unit(values: list[float]) -> np.ndarray:
    a = np.array(values, dtype=np.float32)
    return a / np.linalg.norm(a)


def make_peer(uid: int) -> Peer:
    return Peer(uid=uid, hotkey=f"5FhHotkey{uid:08d}xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")


def make_router(n: int = 15) -> DHTRouter:
    local = make_peer(0)
    r = DHTRouter(local_peer=local)
    for i in range(1, n + 1):
        r.add_peer(make_peer(i))
    return r


# ── Use-case 1: Basic ingest → search ─────────────────────────────────────────

class TestIngestAndSearch:
    """Store a set of vectors and verify search returns the right ones."""

    def setup_method(self) -> None:
        self.store = FAISSStore(dim=4)
        # Represents embeddings for 4 conceptually distinct "memories"
        self.memories = {
            "memory:dogs":   _unit([1.0, 0.2, 0.0, 0.0]),
            "memory:cats":   _unit([0.9, 0.3, 0.1, 0.0]),
            "memory:birds":  _unit([0.0, 1.0, 0.2, 0.0]),
            "memory:fish":   _unit([0.0, 0.1, 1.0, 0.2]),
        }
        for cid, emb in self.memories.items():
            self.store.upsert(VectorRecord(cid=cid, embedding=emb))

    def test_search_returns_semantically_close_result(self) -> None:
        # Query near "dogs" space
        results = self.store.search(_unit([1.0, 0.25, 0.0, 0.0]), top_k=2)
        top_cids = [r.cid for r in results]
        assert "memory:dogs" in top_cids

    def test_all_memories_retrievable(self) -> None:
        for cid in self.memories:
            rec = self.store.get(cid)
            assert rec is not None, f"{cid} not found"

    def test_search_top_k_respected(self) -> None:
        results = self.store.search(_unit([1.0, 0.0, 0.0, 0.0]), top_k=2)
        assert len(results) == 2

    def test_exact_hit_is_first(self) -> None:
        exact = self.memories["memory:fish"]
        results = self.store.search(exact, top_k=4)
        assert results[0].cid == "memory:fish"

    def test_delete_removes_memory(self) -> None:
        self.store.delete("memory:birds")
        assert self.store.get("memory:birds") is None
        results = {r.cid for r in self.store.search(_unit([0.0, 1.0, 0.0, 0.0]), top_k=10)}
        assert "memory:birds" not in results

    def test_update_memory(self) -> None:
        """Upserting a CID with a new vector updates the stored embedding."""
        new_emb = _unit([0.0, 0.0, 0.0, 1.0])
        self.store.upsert(VectorRecord(cid="memory:dogs", embedding=new_emb))
        assert self.store.count() == len(self.memories)  # no new record created
        rec = self.store.get("memory:dogs")
        assert rec is not None
        np.testing.assert_allclose(rec.embedding, new_emb, atol=1e-5)


# ── Use-case 2: CID integrity + storage proof ─────────────────────────────────

@pytest.mark.skipif(not _RUST, reason="engram_core not built")
class TestCIDAndProof:
    """Verify that a stored vector can be proven via the challenge protocol."""

    def setup_method(self) -> None:
        self.store = FAISSStore(dim=4)
        self.emb = _unit([1.0, 0.5, 0.2, 0.1])
        self.cid = engram_core.generate_cid(self.emb.tolist(), {}, "v1")
        self.store.upsert(VectorRecord(cid=self.cid, embedding=self.emb))

    def test_cid_matches_stored_embedding(self) -> None:
        rec = self.store.get(self.cid)
        assert rec is not None
        assert engram_core.verify_cid(self.cid, rec.embedding.tolist(), {}, "v1")

    def test_can_prove_storage(self) -> None:
        challenge = engram_core.generate_challenge(self.cid, 60)
        rec = self.store.get(self.cid)
        response = engram_core.generate_response(challenge, rec.embedding.tolist())
        assert engram_core.verify_response(challenge, response, self.emb.tolist())

    def test_cannot_forge_proof_with_wrong_vector(self) -> None:
        challenge = engram_core.generate_challenge(self.cid, 60)
        wrong_emb = _unit([9.0, 9.0, 9.0, 9.0])
        forged_response = engram_core.generate_response(challenge, wrong_emb.tolist())
        assert not engram_core.verify_response(challenge, forged_response, self.emb.tolist())

    @pytest.mark.skipif(not _BATCH, reason="batch proof API not in installed wheel (rebuild needed)")
    def test_batch_prove_multiple_memories(self) -> None:
        """Validator challenges multiple stored memories in one round trip."""
        embs = [_unit([float(i), 0.0, 0.0, 0.0]) for i in range(1, 6)]
        cids = [engram_core.generate_cid(e.tolist(), {}, "v1") for e in embs]
        for cid, emb in zip(cids, embs):
            self.store.upsert(VectorRecord(cid=cid, embedding=emb))

        batch = engram_core.generate_batch_challenge(cids, 60)
        stored_embs = [self.store.get(cid).embedding.tolist() for cid in cids]
        response = engram_core.generate_batch_response(batch, stored_embs)
        results = engram_core.verify_batch_response(batch, response, stored_embs)
        assert all(results), f"Some proofs failed: {results}"


# ── Use-case 3: Replication + multi-miner failure ─────────────────────────────

class TestReplicationLifecycle:
    """Full replication cycle: ingest → confirm → fail → recover."""

    def setup_method(self) -> None:
        self.router = make_router(20)
        self.mgr = ReplicationManager(router=self.router)

    def test_ingest_assigns_correct_number_of_miners(self) -> None:
        cid = "v1::" + "a" * 64
        rec = self.mgr.register(cid)
        assert len(rec.assigned_uids) == REPLICATION_FACTOR

    def test_fully_replicated_then_healthy(self) -> None:
        cid = "v1::" + "b" * 64
        rec = self.mgr.register(cid)
        for uid in rec.assigned_uids:
            self.mgr.confirm(cid, uid)
        assert rec.status == ReplicationStatus.HEALTHY

    def test_single_miner_fails_creates_repair_task(self) -> None:
        cid = "v1::" + "c" * 64
        rec = self.mgr.register(cid)
        for uid in rec.assigned_uids:
            self.mgr.confirm(cid, uid)

        failed_uid = rec.confirmed_uids[0]
        tasks = self.mgr.handle_miners_offline([failed_uid])
        assert any(t.cid == cid for t in tasks)

    def test_all_replicas_fail_status_is_lost(self) -> None:
        cid = "v1::" + "d" * 64
        rec = self.mgr.register(cid)
        for uid in rec.assigned_uids:
            self.mgr.confirm(cid, uid)

        all_confirmed = list(rec.confirmed_uids)
        self.mgr.handle_miners_offline(all_confirmed)
        assert rec.status == ReplicationStatus.LOST

    def test_repair_plan_covers_all_affected_cids(self) -> None:
        cids = ["v1::" + c * 64 for c in "efghij"]
        confirmed_uids: list[int] = []

        for cid in cids:
            rec = self.mgr.register(cid)
            uid = rec.assigned_uids[0]
            self.mgr.confirm(cid, uid)
            confirmed_uids.append(uid)

        # Take down all confirmed miners at once
        unique_uids = list(set(confirmed_uids))
        tasks = self.mgr.handle_miners_offline(unique_uids)
        repaired = {t.cid for t in tasks}

        for cid in cids:
            rec = self.mgr.get_record(cid)
            if rec and rec.needs_replication:
                assert cid in repaired

    def test_recovery_restores_healthy_status(self) -> None:
        cid = "v1::" + "k" * 64
        rec = self.mgr.register(cid)
        for uid in rec.assigned_uids:
            self.mgr.confirm(cid, uid)

        # Two miners fail
        lost = rec.confirmed_uids[:2]
        tasks = self.mgr.handle_miners_offline(lost)
        task = next(t for t in tasks if t.cid == cid)

        # Repair: confirm on the suggested replacement peers
        for peer in task.targets:
            self.mgr.confirm(cid, peer.uid)

        assert rec.status == ReplicationStatus.HEALTHY


# ── Use-case 4: Private namespace lifecycle ───────────────────────────────────

class TestNamespaceLifecycle:
    """Ingesting into and querying from a private namespace."""

    def setup_method(self) -> None:
        self.store = FAISSStore(dim=4)
        self.ns = "team_memories"
        self.other_ns = "other_team"

    def test_private_ingest_and_retrieve(self) -> None:
        emb = _unit([1.0, 0.0, 0.0, 0.0])
        self.store.upsert(VectorRecord(
            cid="private_cid",
            embedding=emb,
            namespace=self.ns,
        ))
        rec = self.store.get("private_cid", namespace=self.ns)
        assert rec is not None
        assert rec.namespace == self.ns

    def test_private_search_stays_within_namespace(self) -> None:
        emb = _unit([1.0, 0.0, 0.0, 0.0])
        self.store.upsert(VectorRecord(cid="ns_record", embedding=emb, namespace=self.ns))
        self.store.upsert(VectorRecord(cid="public_record", embedding=emb, namespace="__public__"))

        results = {r.cid for r in self.store.search(emb, namespace=self.ns)}
        assert "ns_record" in results
        assert "public_record" not in results

    def test_wrong_namespace_cannot_read_record(self) -> None:
        emb = _unit([1.0, 0.0, 0.0, 0.0])
        self.store.upsert(VectorRecord(cid="secret", embedding=emb, namespace=self.ns))
        assert self.store.get("secret", namespace=self.other_ns) is None
        assert self.store.get("secret", namespace="__public__") is None

    def test_multiple_namespaces_independent(self) -> None:
        """Each namespace sees only its own records even when vectors are identical."""
        emb = _unit([1.0, 0.0, 0.0, 0.0])
        namespaces = ["ns_a", "ns_b", "ns_c"]
        for ns in namespaces:
            self.store.upsert(VectorRecord(cid=f"cid_{ns}", embedding=emb, namespace=ns))

        for ns in namespaces:
            results = {r.cid for r in self.store.search(emb, namespace=ns)}
            assert f"cid_{ns}" in results
            for other in namespaces:
                if other != ns:
                    assert f"cid_{other}" not in results
