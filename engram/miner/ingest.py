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

from engram.config import MAX_METADATA_BYTES, MAX_TEXT_CHARS, CANONICAL_MODEL_VERSION, MIN_INGEST_STAKE_TAO
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
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        subtensor=None,
        netuid: int | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._subtensor = subtensor   # optional — if set, stake check is enforced
        self._netuid = netuid

    def handle(self, synapse: IngestSynapse, caller_hotkey: str | None = None) -> IngestSynapse:
        start = time.perf_counter()

        try:
            self._check_stake(caller_hotkey)
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

    def _resolve_embedding(self, synapse: IngestSynapse) -> np.ndarray:
        if synapse.raw_embedding is not None:
            return np.array(synapse.raw_embedding, dtype=np.float32)
        return self._embedder.embed(synapse.text)
