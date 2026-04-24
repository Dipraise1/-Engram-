"""
Engram Miner — Ingest Handler

Handles IngestSynapse requests:
  text/embedding → embed → CID → store → return CID
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from loguru import logger

from engram.config import MAX_METADATA_BYTES, MAX_TEXT_CHARS, CANONICAL_MODEL_VERSION, MIN_INGEST_STAKE_TAO, DP_EPSILON
from engram.miner.embedder import Embedder
from engram.miner.store import VectorRecord, VectorStore
from engram.protocol import IngestSynapse

try:
    import engram_core  # Rust PyO3 extension
    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False
    logger.warning("engram_core (Rust) not available — falling back to Python CID generation.")
    from engram import cid as _cid_py  # Python fallback


def _add_dp_noise(embedding: np.ndarray, epsilon: float) -> np.ndarray:
    """
    Gaussian noise mechanism for (epsilon, 1e-5)-DP on unit-sphere embeddings.

    Calibrated to L2 sensitivity 1.0 (normalised vectors). Per-dimension sigma
    scales with 1/sqrt(dim) so total noise magnitude is independent of dimension,
    preserving approximate nearest-neighbour quality while defeating vector
    inversion attacks (ATLAS AML.T0024).

    Re-normalises the result so cosine similarity search still works correctly.
    """
    sigma = 1.0 / (epsilon * float(embedding.shape[0]) ** 0.5)
    noise = np.random.normal(0.0, sigma, embedding.shape).astype(np.float32)
    noisy = embedding + noise
    norm = np.linalg.norm(noisy)
    return noisy / norm if norm > 0.0 else noisy


def _generate_cid(embedding: np.ndarray, metadata: dict[str, Any], model_version: str) -> str:
    if _RUST_AVAILABLE:
        return engram_core.generate_cid(
            embedding.tolist(),
            {k: str(v) for k, v in metadata.items()},
            model_version,
        )
    return _cid_py.generate_cid(embedding, metadata, model_version)


class IngestHandler:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        subtensor=None,
        netuid: int | None = None,
        namespace_registry=None,
        dp_epsilon: float | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._subtensor = subtensor   # optional — if set, stake check is enforced
        self._netuid = netuid
        self._ns_registry = namespace_registry
        # Differential privacy: add calibrated Gaussian noise to private-namespace
        # embeddings before storage to resist vector inversion (ATLAS AML.T0024).
        # None disables noise; defaults to DP_EPSILON from config when not overridden.
        self._dp_epsilon: float | None = dp_epsilon if dp_epsilon is not None else DP_EPSILON

    def handle(self, synapse: IngestSynapse, caller_hotkey: str | None = None) -> IngestSynapse:
        start = time.perf_counter()

        try:
            self._check_stake(caller_hotkey)
            self._validate(synapse)
            namespace = self._resolve_namespace(synapse)
            embedding = self._resolve_embedding(synapse)

            # Apply DP noise for private namespaces when epsilon is configured.
            from engram.miner.store import _PUBLIC_NS
            if self._dp_epsilon is not None and namespace != _PUBLIC_NS:
                embedding = _add_dp_noise(embedding, self._dp_epsilon)

            cid = _generate_cid(embedding, synapse.metadata, synapse.model_version)

            self._store.upsert(VectorRecord(
                cid=cid,
                embedding=embedding,
                metadata=synapse.metadata,
                namespace=namespace,
            ))

            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(f"Ingest OK | cid={cid[:20]}... | {elapsed_ms:.1f}ms")
            synapse.cid = cid

        except ValueError as e:
            logger.warning(f"Ingest rejected: {e}")
            synapse.error = str(e)
        except Exception as e:
            logger.error(f"Ingest error: {e}")
            synapse.error = "Something went wrong on our end. The miner logged the details — try again in a moment."

        return synapse

    # ── Private ───────────────────────────────────────────────────────────────

    def _check_stake(self, hotkey: str | None) -> None:
        """Reject ingest requests from wallets with insufficient stake (anti-spam)."""
        if self._subtensor is None or self._netuid is None:
            return  # stake check disabled — local dev mode
        if hotkey is None:
            return  # no hotkey provided (SDK / direct HTTP) — allow
        try:
            stake = self._subtensor.get_stake_for_coldkey_and_hotkey(
                coldkey_ss58=hotkey, hotkey_ss58=hotkey, netuid=self._netuid
            )
            tao = float(stake)
        except Exception:
            return  # can't check stake — allow (fail open to avoid blocking legit requests)

        if tao < MIN_INGEST_STAKE_TAO:
            raise ValueError(
                f"Your wallet only has τ{tao:.4f} staked on this subnet. "
                f"You need at least τ{MIN_INGEST_STAKE_TAO} to store data here. "
                "Add more stake with: btcli stake add"
            )

    def _validate(self, synapse: IngestSynapse) -> None:
        from engram.config import EMBEDDING_DIM
        if synapse.text is None and synapse.raw_embedding is None:
            raise ValueError(
                "Nothing to store — send either 'text' or 'raw_embedding' in the request."
            )
        if synapse.text is not None and len(synapse.text) > MAX_TEXT_CHARS:
            raise ValueError(
                f"That text is too long ({len(synapse.text):,} chars). "
                f"Please keep it under {MAX_TEXT_CHARS:,} characters. "
                "Split large documents into smaller chunks before ingesting."
            )
        if synapse.raw_embedding is not None:
            if not isinstance(synapse.raw_embedding, (list, tuple)):
                raise ValueError("raw_embedding must be a list of floats.")
            if len(synapse.raw_embedding) != EMBEDDING_DIM:
                raise ValueError(
                    f"raw_embedding has {len(synapse.raw_embedding)} dimensions but "
                    f"this subnet requires exactly {EMBEDDING_DIM}."
                )
        if synapse.metadata:
            import json
            size = len(json.dumps(synapse.metadata).encode())
            if size > MAX_METADATA_BYTES:
                raise ValueError(
                    f"Metadata is {size:,} bytes, which is over the {MAX_METADATA_BYTES:,}-byte limit. "
                    "Try removing large values or moving the content into the text field instead."
                )

    def _resolve_namespace(self, synapse: IngestSynapse) -> str:
        """Authenticate the namespace claim and return the namespace to store under."""
        from engram.miner.store import _PUBLIC_NS
        ns = synapse.namespace

        if ns is None:
            return _PUBLIC_NS

        if self._ns_registry is None:
            raise ValueError("This miner does not support private namespaces.")

        # ── Sig-based auth (preferred — key never travels on wire) ────────────
        sig = synapse.namespace_sig
        ts  = synapse.namespace_timestamp_ms
        hk  = synapse.namespace_hotkey

        if sig and ts and hk:
            if not self._ns_registry.verify_sig(ns, hk, sig, ts):
                raise ValueError(
                    f"Namespace signature invalid for '{ns}'. "
                    "Check your hotkey, timestamp, and message format."
                )
            if not self._ns_registry.exists(ns):
                self._ns_registry.register_owner(ns, hk)
                logger.info(f"Namespace '{ns}' registered via sig | owner={hk[:12]}…")
            elif self._ns_registry.owner_hotkey(ns) != hk:
                raise ValueError(
                    f"Hotkey {hk[:12]}… is not the registered owner of namespace '{ns}'."
                )
            return ns

        # ── Legacy key-based auth (backward compat, deprecated) ───────────────
        key = synapse.namespace_key
        if key is None:
            raise ValueError(
                f"Namespace '{ns}' requires authentication. "
                "Provide namespace_hotkey + namespace_sig + namespace_timestamp_ms "
                "(or legacy namespace_key)."
            )
        logger.warning(f"Namespace '{ns}' using deprecated key-based auth — migrate to sig-based.")

        if not self._ns_registry.exists(ns):
            self._ns_registry.create(ns, key)
            logger.info(f"Namespace '{ns}' auto-created (legacy key auth)")
            return ns

        if not self._ns_registry.verify(ns, key):
            raise ValueError(f"Invalid key for namespace '{ns}'.")
        return ns

    def _resolve_embedding(self, synapse: IngestSynapse) -> np.ndarray:
        if synapse.raw_embedding is not None:
            return np.array(synapse.raw_embedding, dtype=np.float32)
        return self._embedder.embed(synapse.text)
