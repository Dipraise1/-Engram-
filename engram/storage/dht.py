"""
Engram — DHT Routing Layer

Kademlia-style Distributed Hash Table for routing CIDs to miners.

Responsibilities:
  - Given a CID, determine which miners should store it (routing)
  - Given a CID, find which miners claim to hold it (lookup)
  - Maintain a routing table of known peers (miners)

Design:
  - XOR distance metric (Kademlia standard)
  - k-bucket routing table (k = DHT_BUCKET_SIZE)
  - Deterministic assignment: same CID always maps to same set of miners
    (important for replication consistency)
  - No network I/O here — this is pure routing logic.
    The Bittensor metagraph provides the peer list.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from engram.config import DHT_ALPHA, DHT_BUCKET_SIZE, REPLICATION_FACTOR


# ── Types ─────────────────────────────────────────────────────────────────────

@dataclass
class Peer:
    """A miner on the network."""
    uid: int                          # Bittensor UID
    hotkey: str                       # SS58 hotkey address
    ip: str = ""
    port: int = 0
    node_id: bytes = field(default_factory=bytes)  # 32-byte DHT identity

    def __post_init__(self) -> None:
        if not self.node_id:
            # Derive node ID deterministically from hotkey
            self.node_id = _hotkey_to_node_id(self.hotkey)

    def __hash__(self) -> int:
        return self.uid

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Peer) and self.uid == other.uid


# ── XOR distance ──────────────────────────────────────────────────────────────

def xor_distance(a: bytes, b: bytes) -> int:
    """XOR distance between two 32-byte node IDs."""
    return int.from_bytes(
        bytes(x ^ y for x, y in zip(a, b)),
        byteorder="big",
    )


def cid_to_key(cid: str) -> bytes:
    """Convert a CID string to a 32-byte DHT key."""
    # Strip version prefix: "v1::abcdef..." → hash the raw hex digest
    raw = cid.split("::", 1)[-1]
    return hashlib.sha256(raw.encode()).digest()


def _hotkey_to_node_id(hotkey: str) -> bytes:
    """Derive a stable 32-byte node ID from a hotkey SS58 address."""
    return hashlib.sha256(hotkey.encode()).digest()


# ── Routing table ─────────────────────────────────────────────────────────────

class RoutingTable:
    """
    Kademlia-style k-bucket routing table.

    Peers are organised into 256 buckets by XOR distance from our own node ID.
    Each bucket holds at most k peers (DHT_BUCKET_SIZE).
    """

    def __init__(self, local_id: bytes) -> None:
        self.local_id = local_id
        self._buckets: list[list[Peer]] = [[] for _ in range(256)]

    def add(self, peer: Peer) -> None:
        """Add or refresh a peer in the routing table."""
        if peer.node_id == self.local_id:
            return  # don't add ourselves

        bucket_idx = self._bucket_index(peer.node_id)
        bucket = self._buckets[bucket_idx]

        # If already known, move to tail (most recently seen)
        existing = next((p for p in bucket if p.uid == peer.uid), None)
        if existing:
            bucket.remove(existing)
            bucket.append(peer)
            return

        if len(bucket) < DHT_BUCKET_SIZE:
            bucket.append(peer)
        # If bucket is full: drop the oldest (head). In production, ping first.

    def remove(self, uid: int) -> None:
        for bucket in self._buckets:
            bucket[:] = [p for p in bucket if p.uid != uid]

    def closest(self, key: bytes, k: int = DHT_BUCKET_SIZE) -> list[Peer]:
        """Return the k peers closest to the given key by XOR distance."""
        all_peers = [p for bucket in self._buckets for p in bucket]
        return sorted(all_peers, key=lambda p: xor_distance(p.node_id, key))[:k]

    def all_peers(self) -> list[Peer]:
        return [p for bucket in self._buckets for p in bucket]

    def size(self) -> int:
        return sum(len(b) for b in self._buckets)

    def _bucket_index(self, node_id: bytes) -> int:
        dist = xor_distance(self.local_id, node_id)
        if dist == 0:
            return 0
        return min(dist.bit_length() - 1, 255)


# ── DHT Router ────────────────────────────────────────────────────────────────

class DHTRouter:
    """
    Main DHT interface used by the miner and validator.

    Given a CID, tells you:
      - which miners should store it (assign)
      - which miners to query for it (lookup)
    """

    def __init__(self, local_peer: Peer) -> None:
        self._local = local_peer
        self._table = RoutingTable(local_id=local_peer.node_id)

    # ── Peer management ───────────────────────────────────────────────────────

    def add_peer(self, peer: Peer) -> None:
        self._table.add(peer)

    def remove_peer(self, uid: int) -> None:
        self._table.remove(uid)

    def peer_count(self) -> int:
        return self._table.size()

    def sync_from_metagraph(self, axons: list, uids: list[int]) -> None:
        """
        Populate routing table from a Bittensor metagraph snapshot.

        Args:
            axons: list of bt.AxonInfo objects from metagraph.axons
            uids:  list of UIDs from metagraph.uids
        """
        for uid, axon in zip(uids, axons):
            peer = Peer(
                uid=int(uid),
                hotkey=axon.hotkey,
                ip=axon.ip,
                port=axon.port,
            )
            self.add_peer(peer)

    # ── Routing ───────────────────────────────────────────────────────────────

    def assign(self, cid: str, replication: int = REPLICATION_FACTOR) -> list[Peer]:
        """
        Deterministically assign a CID to `replication` miners.

        Returns the same set of peers for the same CID regardless of
        which node calls this — this is the core DHT guarantee.
        """
        key = cid_to_key(cid)
        return self._table.closest(key, k=replication)

    def lookup(self, cid: str, alpha: int = DHT_ALPHA) -> list[Peer]:
        """
        Find the miners most likely to hold a CID.

        In a full Kademlia implementation this would be an iterative
        network lookup. Here we return the closest peers from our
        local routing table — sufficient for a single-process subnet.
        """
        key = cid_to_key(cid)
        return self._table.closest(key, k=alpha)

    def should_store(self, cid: str, replication: int = REPLICATION_FACTOR) -> bool:
        """
        Returns True if this node is one of the assigned miners for a CID.
        Miners call this to decide whether to accept an ingest request.

        Includes the local peer in the candidate pool alongside routing table peers.
        """
        key = cid_to_key(cid)
        all_peers = self._table.all_peers() + [self._local]
        candidates = sorted(all_peers, key=lambda p: xor_distance(p.node_id, key))[:replication]
        return any(p.uid == self._local.uid for p in candidates)

    def all_peers(self) -> list[Peer]:
        return self._table.all_peers()

    def get_peers_for_uids(self, uids: list[int]) -> list[Peer]:
        """Return Peer objects for the given UIDs (skips UIDs not in routing table)."""
        uid_set = set(uids)
        return [p for p in self._table.all_peers() if p.uid in uid_set]
