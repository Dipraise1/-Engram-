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

from engram.config import MAX_METADATA_BYTES, MAX_TEXT_CHARS, CANONICAL_MODEL_VERSION
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


def _generate_cid(embedding: np.ndarray, metadata: dict[str, Any], model_version: str) -> str:
    if _RUST_AVAILABLE:
        return engram_core.generate_cid(
            embedding.tolist(),
            {k: str(v) for k, v in metadata.items()},
            model_version,
        )
    return _cid_py.generate_cid(embedding, metadata, model_version)


class IngestHandler:
    def __init__(self, store: VectorStore, embedder: Embedder) -> None:
        self._store = store
        self._embedder = embedder

    def handle(self, synapse: IngestSynapse) -> IngestSynapse:
        start = time.perf_counter()

        try:
            self._validate(synapse)
            embedding = self._resolve_embedding(synapse)
            cid = _generate_cid(embedding, synapse.metadata, synapse.model_version)

            self._store.upsert(VectorRecord(
                cid=cid,
                embedding=embedding,
                metadata=synapse.metadata,
            ))

            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(f"Ingest OK | cid={cid[:20]}... | {elapsed_ms:.1f}ms")
            synapse.cid = cid

        except ValueError as e:
            logger.warning(f"Ingest rejected: {e}")
            synapse.error = str(e)
        except Exception as e:
            logger.error(f"Ingest error: {e}")
            synapse.error = "internal error"

        return synapse

    # ── Private ───────────────────────────────────────────────────────────────

    def _validate(self, synapse: IngestSynapse) -> None:
        if synapse.text is None and synapse.raw_embedding is None:
            raise ValueError("Either 'text' or 'raw_embedding' must be provided.")
        if synapse.text is not None and len(synapse.text) > MAX_TEXT_CHARS:
            raise ValueError(f"Text exceeds maximum length of {MAX_TEXT_CHARS} chars.")
        if synapse.metadata:
            import json
            if len(json.dumps(synapse.metadata).encode()) > MAX_METADATA_BYTES:
                raise ValueError(f"Metadata exceeds {MAX_METADATA_BYTES} bytes.")

    def _resolve_embedding(self, synapse: IngestSynapse) -> np.ndarray:
        if synapse.raw_embedding is not None:
            return np.array(synapse.raw_embedding, dtype=np.float32)
        return self._embedder.embed(synapse.text)
