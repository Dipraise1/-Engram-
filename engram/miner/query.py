"""
Engram Miner — Query Handler

Handles QuerySynapse requests:
  query_text/vector → ANN search → return top-K results
"""

from __future__ import annotations

import time

import numpy as np
from loguru import logger

from engram.config import DEFAULT_TOP_K
from engram.miner.embedder import Embedder
from engram.miner.store import VectorStore
from engram.protocol import QuerySynapse


class QueryHandler:
    def __init__(self, store: VectorStore, embedder: Embedder) -> None:
        self._store = store
        self._embedder = embedder

    def handle(self, synapse: QuerySynapse) -> QuerySynapse:
        start = time.perf_counter()

        try:
            query_vec = self._resolve_query(synapse)
            results = self._store.search(query_vec, top_k=synapse.top_k or DEFAULT_TOP_K)

            elapsed_ms = (time.perf_counter() - start) * 1000

            synapse.results = [
                {"cid": r.cid, "score": r.score, "metadata": r.metadata}
                for r in results
            ]
            synapse.latency_ms = elapsed_ms

            logger.info(f"Query OK | hits={len(results)} | {elapsed_ms:.1f}ms")

        except ValueError as e:
            logger.warning(f"Query rejected: {e}")
            synapse.error = str(e)
            synapse.results = []
        except Exception as e:
            logger.error(f"Query error: {e}")
            synapse.error = "internal error"
            synapse.results = []

        return synapse

    def _resolve_query(self, synapse: QuerySynapse) -> np.ndarray:
        if synapse.query_vector is not None:
            return np.array(synapse.query_vector, dtype=np.float32)
        if synapse.query_text is not None:
            return self._embedder.embed(synapse.query_text)
        raise ValueError("Either 'query_text' or 'query_vector' must be provided.")
