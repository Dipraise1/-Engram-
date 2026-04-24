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
    def __init__(self, store: VectorStore, embedder: Embedder, namespace_registry=None, attestation_registry=None) -> None:
        self._store = store
        self._embedder = embedder
        self._ns_registry = namespace_registry
        self._att_registry = attestation_registry

    def handle(self, synapse: QuerySynapse) -> QuerySynapse:
        from engram.miner.store import _PUBLIC_NS
        from engram.miner.attestation import TrustTier
        start = time.perf_counter()

        try:
            namespace  = self._resolve_namespace(synapse)
            query_vec  = self._resolve_query(synapse)
            results    = self._store.search(query_vec, top_k=synapse.top_k or DEFAULT_TOP_K, namespace=namespace)

            elapsed_ms = (time.perf_counter() - start) * 1000

            # Attach trust tier to every result so agents can filter by trust
            trust_tier = TrustTier.ANONYMOUS
            if self._att_registry is not None:
                trust_tier = self._att_registry.trust_tier(namespace)

            synapse.results = [
                {
                    "cid":        r.cid,
                    "score":      r.score,
                    "metadata":   r.metadata,
                    "trust_tier": trust_tier.value,
                }
                for r in results
            ]
            synapse.latency_ms = elapsed_ms

            logger.info(f"Query OK | ns={namespace} | tier={trust_tier.value} | hits={len(results)} | {elapsed_ms:.1f}ms")

        except ValueError as e:
            logger.warning(f"Query rejected: {e}")
            synapse.error = str(e)
            synapse.results = []
        except Exception as e:
            logger.error(f"Query error: {e}")
            synapse.error = "internal error"
            synapse.results = []

        return synapse

    def _resolve_namespace(self, synapse: QuerySynapse) -> str:
        from engram.miner.store import _PUBLIC_NS
        ns = synapse.namespace

        if ns is None:
            return _PUBLIC_NS

        if self._ns_registry is None:
            raise ValueError("This miner does not support private namespaces.")

        # ── Sig-based auth (preferred) ────────────────────────────────────────
        sig = synapse.namespace_sig
        ts  = synapse.namespace_timestamp_ms
        hk  = synapse.namespace_hotkey

        if sig and ts and hk:
            if not self._ns_registry.verify_sig(ns, hk, sig, ts):
                raise ValueError(f"Namespace signature invalid for '{ns}'.")
            if not self._ns_registry.exists(ns):
                raise ValueError(f"Namespace '{ns}' does not exist.")
            if self._ns_registry.owner_hotkey(ns) != hk:
                raise ValueError(f"Hotkey {hk[:12]}… is not the registered owner of namespace '{ns}'.")
            return ns

        # ── Legacy key-based auth (deprecated) ────────────────────────────────
        key = synapse.namespace_key
        if key is None:
            raise ValueError(
                f"Namespace '{ns}' requires authentication. "
                "Provide namespace_hotkey + namespace_sig + namespace_timestamp_ms."
            )
        if not self._ns_registry.exists(ns):
            raise ValueError(f"Namespace '{ns}' does not exist.")
        if not self._ns_registry.verify(ns, key):
            raise ValueError(f"Invalid key for namespace '{ns}'.")
        return ns

    def _resolve_query(self, synapse: QuerySynapse) -> np.ndarray:
        if synapse.query_vector is not None:
            return np.array(synapse.query_vector, dtype=np.float32)
        if synapse.query_text is not None:
            return self._embedder.embed(synapse.query_text)
        raise ValueError("Either 'query_text' or 'query_vector' must be provided.")
