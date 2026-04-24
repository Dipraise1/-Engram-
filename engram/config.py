"""
Engram Subnet — Global Configuration
All subnet-wide constants live here. Never hardcode these elsewhere.
"""
import os
from typing import Literal

# ── Identity ───────────────────────────────────────────────────────────────────
SUBNET_NAME = "engram"
SUBNET_VERSION = "0.1.2"
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
MIN_CHALLENGES_BEFORE_SLASH: int = 5   # minimum sample size before a miner can be slashed
MAX_KNOWN_CIDS: int = 100_000          # cap to prevent unbounded memory growth

# ── Namespace Attestation — Trust Tiers ───────────────────────────────────────
# Stake thresholds (TAO) that determine how much an agent should trust content
# written to a namespace. The chain is the authority — no central moderation.
TRUST_TIER_SOVEREIGN:  float = 1000.0   # protocol-level trusted entities
TRUST_TIER_VERIFIED:   float = 100.0    # significant economic accountability
TRUST_TIER_COMMUNITY:  float = 1.0      # basic skin in the game
# Below COMMUNITY = "anonymous" — no stake, no guarantees

# How often to refresh a namespace owner's stake from the metagraph (seconds)
ATTESTATION_STAKE_REFRESH_SECS: int = 600

# ── Anti-spam ──────────────────────────────────────────────────────────────────
MIN_INGEST_STAKE_TAO: float = 0.001
MAX_METADATA_BYTES: int = 4096
MAX_TEXT_CHARS: int = 8192

# ── Arweave permanent media storage ───────────────────────────────────────────
# Set ARWEAVE_KEY (JWK JSON) to enable; ingest_image/pdf/url will store raw
# media on Arweave and include arweave_tx_id + arweave_url in vector metadata.
ARWEAVE_GATEWAY_URL: str = os.getenv("ARWEAVE_GATEWAY_URL", "https://arweave.net")

# ── Differential privacy for private namespace embeddings ─────────────────────
# Gaussian mechanism (ATLAS AML.T0024 — vector inversion defence).
# Lower epsilon = stronger privacy, slightly lower recall.
# 3.0 is a good default for 1536-dim embeddings. Set DP_EPSILON=none to disable.
_dp_env = os.getenv("DP_EPSILON", "3.0").strip().lower()
DP_EPSILON: float | None = None if _dp_env in ("0", "none", "false", "") else float(_dp_env)

# ── Security ───────────────────────────────────────────────────────────────────
# REQUIRE_HOTKEY_SIG=true  — reject requests without a valid sr25519 signature
# REQUIRE_HOTKEY_SIG=false — warn but allow (default; backward compatible)
# ALLOWED_VALIDATOR_HOTKEYS — comma-separated SS58 hotkeys permitted to call the miner
#   Leave empty to allow all hotkeys (still subject to stake check + rate limit).
# See engram/miner/auth.py for the signing protocol.

# ── DHT ───────────────────────────────────────────────────────────────────────
DHT_BUCKET_SIZE: int = 20
DHT_ALPHA: int = 3

# ── Timeouts ───────────────────────────────────────────────────────────────────
QUERY_TIMEOUT_SECS: int = 30
INGEST_TIMEOUT_SECS: int = 60

VectorBackend = Literal["qdrant", "faiss"]
