"""
Engram CID — Content Identifier for Embeddings

Format: "v1::<sha256(embedding_bytes + canonical_metadata_bytes)>"

Guarantees:
- Same text + same model version always produces the same CID
- Different text OR different model version always produces a different CID
- CIDs are version-prefixed so future model migrations don't collide
"""

import hashlib
import json
from typing import Any

import numpy as np

from engram.config import CID_SEPARATOR, CID_VERSION_PREFIX, CANONICAL_MODEL_VERSION


def _canonical_metadata(metadata: dict[str, Any]) -> bytes:
    """Deterministic JSON serialization of metadata for hashing.
    Uses separators=(',',':') to match Rust serde_json output (no spaces).
    """
    return json.dumps(metadata, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":")).encode("utf-8")


def generate_cid(
    embedding: np.ndarray,
    metadata: dict[str, Any] | None = None,
    model_version: str = CANONICAL_MODEL_VERSION,
) -> str:
    """
    Generate a content identifier for an embedding.

    Args:
        embedding:     The embedding vector as a numpy array.
        metadata:      Optional metadata dict included in the hash.
        model_version: Subnet epoch model version (default: current canonical).

    Returns:
        CID string in the form "v1::<64-char sha256 hex>"
    """
    if metadata is None:
        metadata = {}

    # Normalize: float32, contiguous memory
    vec = np.asarray(embedding, dtype=np.float32)
    vec_bytes = vec.tobytes()

    meta_bytes = _canonical_metadata({"model_version": model_version, **metadata})

    digest = hashlib.sha256(vec_bytes + meta_bytes).hexdigest()
    return f"{CID_VERSION_PREFIX}{CID_SEPARATOR}{digest}"


def verify_cid(
    cid: str,
    embedding: np.ndarray,
    metadata: dict[str, Any] | None = None,
    model_version: str = CANONICAL_MODEL_VERSION,
) -> bool:
    """Verify that a CID matches the given embedding and metadata."""
    expected = generate_cid(embedding, metadata, model_version)
    return cid == expected


def parse_cid(cid: str) -> tuple[str, str]:
    """
    Parse a CID into (version, hash).

    Returns:
        (version_prefix, sha256_hex)

    Raises:
        ValueError: if the CID format is invalid.
    """
    parts = cid.split(CID_SEPARATOR, 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid CID format: {cid!r}")
    version, digest = parts
    if len(digest) != 64:
        raise ValueError(f"CID hash must be 64 hex chars, got {len(digest)}: {cid!r}")
    return version, digest


def cid_version(cid: str) -> str:
    """Return the version prefix of a CID."""
    version, _ = parse_cid(cid)
    return version
