"""
Engram Python SDK

Simple client for interacting with the Engram subnet.

Usage:
    from engram.sdk.client import EngramClient
    import bittensor as bt

    wallet = bt.wallet()
    client = EngramClient(wallet=wallet, netuid=99)

    cid = client.ingest("The transformer architecture introduced in 2017...")
    results = client.query("attention mechanism in neural networks", top_k=10)
"""

from __future__ import annotations

from typing import Any

import bittensor as bt
import numpy as np
from loguru import logger

from engram.protocol import IngestSynapse, QuerySynapse


class EngramClient:
    """
    High-level client for reading from and writing to the Engram subnet.
    """

    def __init__(
        self,
        wallet: bt.wallet,
        netuid: int = 99,
        network: str = "finney",
    ) -> None:
        self._wallet = wallet
        self._netuid = netuid
        self._subtensor = bt.subtensor(network=network)
        self._metagraph = self._subtensor.metagraph(netuid=netuid)
        self._dendrite = bt.dendrite(wallet=wallet)

    def refresh(self) -> None:
        """Sync metagraph to latest state."""
        self._metagraph.sync(subtensor=self._subtensor)

    # ── Write ─────────────────────────────────────────────────────────────────

    def ingest(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        broadcast: bool = True,
    ) -> str | None:
        """
        Store text in the Engram network.

        Args:
            text:      The text to embed and store.
            metadata:  Optional metadata dict.
            broadcast: If True, send to multiple miners (replication).

        Returns:
            CID string if successful, None if all miners failed.
        """
        synapse = IngestSynapse(text=text, metadata=metadata or {})
        axons = self._metagraph.axons

        if not axons:
            logger.error("No axons found on metagraph. Did you sync?")
            return None

        targets = axons if broadcast else axons[:1]

        responses = self._dendrite.query(
            axons=targets,
            synapse=synapse,
            deserialize=False,
            timeout=60,
        )

        for r in responses:
            if r and r.cid:
                logger.success(f"Ingested | cid={r.cid[:24]}...")
                return r.cid

        logger.error("Ingest failed — no miner returned a CID.")
        return None

    def ingest_embedding(
        self,
        embedding: list[float] | np.ndarray,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Store a pre-computed embedding vector."""
        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()
        synapse = IngestSynapse(raw_embedding=embedding, metadata=metadata or {})
        axons = self._metagraph.axons[:3]

        responses = self._dendrite.query(
            axons=axons, synapse=synapse, deserialize=False, timeout=60
        )
        for r in responses:
            if r and r.cid:
                return r.cid
        return None

    # ── Read ──────────────────────────────────────────────────────────────────

    def query(
        self,
        text: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Semantic search over the Engram network.

        Returns:
            List of {cid, score, metadata} dicts, best-first.
        """
        synapse = QuerySynapse(query_text=text, top_k=top_k)
        axons = self._metagraph.axons

        if not axons:
            return []

        responses = self._dendrite.query(
            axons=axons,
            synapse=synapse,
            deserialize=False,
            timeout=30,
        )

        # Aggregate and deduplicate results from all miners
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []

        for r in responses:
            if not r or r.error:
                continue
            for item in r.results or []:
                cid = item.get("cid")
                if cid and cid not in seen:
                    seen.add(cid)
                    merged.append(item)

        # Sort by score descending
        merged.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return merged[:top_k]

    def query_by_vector(
        self,
        vector: list[float] | np.ndarray,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search using a raw embedding vector."""
        if isinstance(vector, np.ndarray):
            vector = vector.tolist()
        synapse = QuerySynapse(query_vector=vector, top_k=top_k)
        axons = self._metagraph.axons

        responses = self._dendrite.query(
            axons=axons, synapse=synapse, deserialize=False, timeout=30
        )

        seen: set[str] = set()
        merged = []
        for r in responses:
            if not r or r.error:
                continue
            for item in r.results or []:
                cid = item.get("cid")
                if cid and cid not in seen:
                    seen.add(cid)
                    merged.append(item)

        merged.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return merged[:top_k]
