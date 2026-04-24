"""
Engram Protocol — Bittensor Synapse definitions

Three synapses define all miner/validator communication:
  1. IngestSynapse   — validator/user sends text → miner embeds + stores → returns CID
  2. QuerySynapse    — validator/user sends query → miner returns top-K results
  3. ChallengeSynapse — validator challenges miner to prove it holds a CID
"""

from __future__ import annotations

from typing import Any

import bittensor as bt
from pydantic import Field


# ── 1. Ingest ──────────────────────────────────────────────────────────────────

class IngestSynapse(bt.Synapse):
    """
    Sent by client/validator to a miner to store an embedding.

    Request:  text OR raw_embedding (one must be provided)
    Response: cid (set by miner on success)

    Private collections — two auth modes (prefer sig-based):
      Sig-based  (secure):  namespace + namespace_hotkey + namespace_sig + namespace_timestamp_ms
      Key-based  (legacy):  namespace + namespace_key
    """

    # Request fields
    text: str | None = Field(
        default=None,
        description="Raw text to embed and store. Mutually exclusive with raw_embedding.",
    )
    raw_embedding: list[float] | None = Field(
        default=None,
        description="Pre-computed embedding vector. Skips the embedding step on the miner.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata stored alongside the vector.",
    )
    model_version: str = Field(
        default="v1",
        description="Subnet model epoch version for CID generation.",
    )
    namespace: str | None = Field(
        default=None,
        description="Private collection name.",
    )
    # ── Sig-based namespace auth (preferred) ──────────────────────────────────
    namespace_hotkey: str | None = Field(
        default=None,
        description="Bittensor SS58 hotkey that owns this namespace.",
    )
    namespace_sig: str | None = Field(
        default=None,
        description="sr25519 hex signature over 'engram-ns:{namespace}:{namespace_timestamp_ms}'. "
                    "Replaces namespace_key — key never travels over the wire.",
    )
    namespace_timestamp_ms: int | None = Field(
        default=None,
        description="Unix ms timestamp for namespace_sig replay prevention (±60s window).",
    )
    # ── Legacy key-based auth (deprecated, backward compat) ───────────────────
    namespace_key: str | None = Field(
        default=None,
        description="[Deprecated] Secret key for the namespace. Use namespace_sig instead.",
    )

    # Response fields (miner writes these)
    cid: str | None = Field(default=None, description="Content identifier returned by the miner.")
    error: str | None = Field(default=None, description="Error message if ingest failed.")

    def deserialize(self) -> Any:
        return self.cid


# ── 2. Query ───────────────────────────────────────────────────────────────────

class QueryResult(bt.Synapse):
    """A single result item in a query response."""
    cid: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuerySynapse(bt.Synapse):
    """
    Sent by validator/client to miners for approximate nearest-neighbor search.

    Request:  query_text OR query_vector, top_k
    Response: results (list of CID + score + metadata)
    """

    # Request fields
    query_text: str | None = Field(default=None)
    query_vector: list[float] | None = Field(default=None)
    top_k: int = Field(default=10, ge=1, le=100)
    namespace: str | None = Field(default=None)
    # ── Sig-based namespace auth (preferred) ──────────────────────────────────
    namespace_hotkey: str | None = Field(default=None)
    namespace_sig: str | None = Field(default=None)
    namespace_timestamp_ms: int | None = Field(default=None)
    # ── Legacy key-based auth (deprecated) ────────────────────────────────────
    namespace_key: str | None = Field(default=None)

    # Response fields (miner writes these)
    results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of {cid, score, metadata} dicts ordered by descending similarity.",
    )
    latency_ms: float | None = Field(
        default=None,
        description="Miner-reported query latency in milliseconds.",
    )
    error: str | None = Field(default=None)

    def deserialize(self) -> Any:
        return self.results


# ── 3. Storage Proof Challenge ─────────────────────────────────────────────────

class ChallengeSynapse(bt.Synapse):
    """
    Validator issues a storage proof challenge to a miner.

    Request:  cid + nonce_hex + expires_at
    Response: embedding_hash + proof (HMAC)

    The Rust engram_core module handles challenge generation and verification.
    """

    # Request fields (validator writes)
    cid: str = Field(description="CID the miner is being challenged to prove storage of.")
    nonce_hex: str = Field(description="32-byte random nonce as hex string.")
    expires_at: int = Field(description="Unix timestamp after which the proof is invalid.")

    # Response fields (miner writes)
    embedding_hash: str | None = Field(
        default=None,
        description="SHA-256 of the stored embedding bytes (hex).",
    )
    proof: str | None = Field(
        default=None,
        description="HMAC-SHA256(nonce || embedding_hash) proving possession.",
    )
    error: str | None = Field(default=None)

    def deserialize(self) -> Any:
        return {"embedding_hash": self.embedding_hash, "proof": self.proof}
