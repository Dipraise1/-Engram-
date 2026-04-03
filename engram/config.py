"""
Engram Subnet — Global Configuration
All subnet-wide constants live here. Never hardcode these elsewhere.
"""
import os
from typing import Literal

# ── Identity ───────────────────────────────────────────────────────────────────
SUBNET_NAME = "engram"
SUBNET_VERSION = "0.1.0"
SPEC_VERSION = 100  # bump on any breaking protocol change

# ── Canonical Embedding Model (locked per subnet epoch) ───────────────────────
CANONICAL_MODEL: str = os.getenv("LOCAL_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))
CANONICAL_MODEL_VERSION: str = "v1"

# ── CID ────────────────────────────────────────────────────────────────────────
CID_VERSION_PREFIX: str = "v1"
CID_SEPARATOR: str = "::"

# ── Vector Index (HNSW) ────────────────────────────────────────────────────────
HNSW_M: int = 16
HNSW_EF_CONSTRUCTION: int = 200
HNSW_EF_SEARCH: int = 64
DEFAULT_TOP_K: int = 10

# ── Replication ────────────────────────────────────────────────────────────────
REPLICATION_FACTOR: int = 3

# ── Scoring Weights ────────────────────────────────────────────────────────────
SCORE_ALPHA: float = 0.50   # recall@K
SCORE_BETA: float = 0.30    # latency
SCORE_GAMMA: float = 0.20   # storage proof success rate

RECALL_K: int = 10
LATENCY_BASELINE_MS: float = 500.0
LATENCY_TARGET_MS: float = 100.0

# ── Storage Proofs ─────────────────────────────────────────────────────────────
CHALLENGE_INTERVAL_SECS: int = 300
CHALLENGE_TIMEOUT_SECS: int = 10
CHALLENGE_NONCE_BYTES: int = 32
SLASH_THRESHOLD: float = 0.5

# ── Anti-spam ──────────────────────────────────────────────────────────────────
MIN_INGEST_STAKE_TAO: float = 0.001
MAX_METADATA_BYTES: int = 4096
MAX_TEXT_CHARS: int = 8192

# ── DHT ───────────────────────────────────────────────────────────────────────
DHT_BUCKET_SIZE: int = 20
DHT_ALPHA: int = 3

# ── Timeouts ───────────────────────────────────────────────────────────────────
QUERY_TIMEOUT_SECS: int = 30
INGEST_TIMEOUT_SECS: int = 60

VectorBackend = Literal["qdrant", "faiss"]
