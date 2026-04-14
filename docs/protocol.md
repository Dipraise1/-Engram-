# Protocol Specification

This document describes the wire protocol, content addressing scheme, storage proof system, and scoring formulas that define the Engram subnet.

---

## Synapses

All miner/validator communication uses three HTTP endpoints. The validator (and SDK) POST JSON; the miner responds with JSON.

### IngestSynapse — `POST /IngestSynapse`

Store an embedding on the miner.

**Request:**

```json
{
  "text": "The attention mechanism in transformers...",
  "raw_embedding": null,
  "metadata": {"source": "arxiv"},
  "model_version": "v1"
}
```

Either `text` or `raw_embedding` must be provided. If `text` is given, the miner embeds it using the canonical model. If `raw_embedding` is given, it is stored directly (the embed step is skipped).

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `text` | `string \| null` | One of text/raw_embedding | Max 8192 chars |
| `raw_embedding` | `float[] \| null` | One of text/raw_embedding | Must match `EMBEDDING_DIM` (1536) |
| `metadata` | `object` | No | Max 4096 bytes (JSON-encoded) |
| `model_version` | `string` | No | Default `"v1"` |

**Response:**

```json
{
  "cid": "v1::a3f2b1c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2",
  "error": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `cid` | `string \| null` | Content identifier (set on success) |
| `error` | `string \| null` | Error message (set on failure) |

**HTTP status codes:** `200` (success or miner-level error), `429` (rate limited), `500` (internal error)

---

### QuerySynapse — `POST /QuerySynapse`

Approximate nearest-neighbor search.

**Request:**

```json
{
  "query_text": "how does self-attention work?",
  "query_vector": null,
  "top_k": 10
}
```

Either `query_text` or `query_vector` must be provided.

| Field | Type | Constraints |
|-------|------|-------------|
| `query_text` | `string \| null` | — |
| `query_vector` | `float[] \| null` | Must match `EMBEDDING_DIM` |
| `top_k` | `int` | 1–100, default 10 |

**Response:**

```json
{
  "results": [
    {"cid": "v1::a3f2b1...", "score": 0.9821, "metadata": {"source": "arxiv"}},
    {"cid": "v1::b4c5d6...", "score": 0.9743, "metadata": {}}
  ],
  "latency_ms": 12.4,
  "error": null
}
```

Results are ordered by descending cosine similarity score (0–1).

---

### ChallengeSynapse — `POST /ChallengeSynapse`

Storage proof challenge-response. The validator proves the miner actually holds a CID's embedding.

**Request:**

```json
{
  "cid": "v1::a3f2b1...",
  "nonce_hex": "e3b0c44298fc1c149afb4c8996fb92427ae41e4649b934ca495991b7852b855",
  "expires_at": 1735000030
}
```

| Field | Type | Description |
|-------|------|-------------|
| `cid` | `string` | CID to prove storage of |
| `nonce_hex` | `string` | 32-byte random nonce as hex |
| `expires_at` | `int` | Unix timestamp; miner rejects if `now > expires_at` |

**Response:**

```json
{
  "embedding_hash": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
  "proof": "b94d27b9934d3e08a52e52d7da7dabfac484efe04294e576f80b8a5f1e9e3e5a"
}
```

| Field | Description |
|-------|-------------|
| `embedding_hash` | `SHA-256(little-endian f32 bytes of embedding)` |
| `proof` | `HMAC-SHA256(key=nonce_bytes, msg=embedding_hash_hex)` |

**Verification (validator side):**

1. Recompute `embedding_hash` from the expected embedding
2. Recompute `proof = HMAC-SHA256(nonce, expected_hash)`
3. Compare with miner's response (constant-time comparison)

---

## Content Identifier (CID)

### Format

```
v1::<sha256_hex>
```

Example: `v1::a3f2b1c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2`

### Generation Algorithm

```
1. Serialize embedding as little-endian IEEE-754 float32 bytes
   bytes = struct.pack(f"<{len(embedding)}f", *embedding)

2. Hash the bytes
   emb_hash = sha256(bytes).hexdigest()

3. Serialize metadata as sorted key=value pairs
   meta_str = ";".join(f"{k}={v}" for k, v in sorted(metadata.items()))

4. Combine with model version
   input = f"{emb_hash}|{meta_str}|{model_version}"

5. Final CID
   cid = f"v1::{sha256(input.encode()).hexdigest()}"
```

**Properties:**
- Deterministic: same embedding + metadata + version always produces the same CID
- Content-addressed: any mutation (even 1 bit) produces a different CID
- Version-pinned: CIDs from different model versions are distinct
- Python and Rust implementations produce identical output

---

## Storage Proof

### Purpose

Storage proofs allow validators to verify that a miner actually holds the bytes of a stored embedding, not just its CID. A miner that discards data after ingesting it cannot pass a proof challenge.

### Challenge Construction

```python
nonce = os.urandom(32)       # 32 random bytes
expires_at = int(time.time()) + CHALLENGE_TIMEOUT_SECS   # default +10s
```

### Miner Response

```python
# 1. Look up stored embedding by CID
embedding = store.get(cid).embedding

# 2. Hash the embedding bytes
emb_bytes = struct.pack(f"<{len(embedding)}f", *embedding)
embedding_hash = sha256(emb_bytes).hexdigest()

# 3. Compute HMAC proof
proof = hmac.new(nonce_bytes, embedding_hash.encode(), sha256).hexdigest()
```

### Validator Verification

```python
# Recompute from expected embedding (from ground truth)
expected_hash = sha256(struct.pack(f"<{N}f", *expected_embedding)).hexdigest()

# Recompute expected proof
expected_proof = hmac.new(nonce_bytes, expected_hash.encode(), sha256).hexdigest()

# Constant-time comparison
passed = hmac.compare_digest(expected_proof, response_proof)
       and hmac.compare_digest(expected_hash, response_embedding_hash)
```

If the miner stored the correct embedding, both hashes match. If the miner stored a different vector (or nothing), the HMAC diverges.

---

## Scoring Formula

```
composite_score = α × recall@10
               + β × latency_score
               + γ × proof_success_rate
```

Default weights (from `engram/config.py`):

| Parameter | Value | Config constant |
|-----------|-------|-----------------|
| α (recall weight) | 0.50 | `SCORE_ALPHA` |
| β (latency weight) | 0.30 | `SCORE_BETA` |
| γ (proof weight) | 0.20 | `SCORE_GAMMA` |

### recall@10

```
recall@10 = |top_10_returned ∩ top_10_ground_truth| / min(10, |ground_truth|)
```

### latency_score

```
                  1.0                          if latency_ms ≤ 100
latency_score = { 1.0 − (ms − 100) / 400      if 100 < ms < 500
                  0.0                          if latency_ms ≥ 500
```

Target: `LATENCY_TARGET_MS = 100`
Baseline: `LATENCY_BASELINE_MS = 500`

### proof_success_rate

```
proof_success_rate = passed_challenges / total_challenges_issued
```

### Slashing

Miners with `proof_success_rate < SLASH_THRESHOLD` (default 0.50) receive weight 0, regardless of recall and latency.

### Weight Normalisation

On-chain weights must sum to 1.0:

```
normalised_weight[uid] = score[uid] / sum(all scores)
```

Miners with score 0 receive weight 0 and earn no emissions.

---

## Namespace Attestation

Namespace attestation links a namespace to a Bittensor hotkey. The hotkey's
on-chain TAO stake becomes a publicly verifiable trust signal — no central
moderation required.

### Trust Tiers

| Tier | Stake required | Meaning |
|------|---------------|---------|
| `sovereign` | ≥ 1000 TAO | Protocol-level trusted entity |
| `verified` | ≥ 100 TAO | Significant economic accountability |
| `community` | ≥ 1 TAO | Basic skin in the game |
| `anonymous` | < 1 TAO or unattested | No guarantees |

Stake is refreshed from the metagraph every 600 seconds. If the owner's stake
drops below their tier threshold, the tier degrades automatically.

### POST /AttestNamespace

Link a namespace to a hotkey. Anyone can call this endpoint, but only the
hotkey owner can produce a valid sr25519 signature.

**Request:**

```json
{
  "namespace":    "my_agent_memory",
  "owner_hotkey": "5FakeHotkey...",
  "signature":    "0xabc123...",
  "timestamp_ms": 1712345678123
}
```

The signature must be a sr25519 signature over the canonical message:

```
f"engram-attest:{namespace}:{timestamp_ms}"
```

Timestamp must be within ±60 seconds of server time (replay protection).

**Response:**

```json
{
  "ok": true,
  "namespace": "my_agent_memory",
  "trust_tier": "verified",
  "stake_tao": 250.0
}
```

### GET /attestation/{namespace}

Check the trust tier of any namespace.

**Response (attested):**

```json
{
  "namespace":    "my_agent_memory",
  "owner_hotkey": "5FakeHotkey...",
  "trust_tier":   "verified",
  "stake_tao":    250.0,
  "attested_at":  1712345678.0,
  "attested":     true
}
```

**Response (unattested):**

```json
{
  "namespace":  "unknown_ns",
  "trust_tier": "anonymous",
  "attested":   false
}
```

### trust_tier in query results

Every query result now includes a `trust_tier` field:

```json
{
  "results": [
    {
      "cid":        "v1::a3f2b1...",
      "score":      0.9821,
      "metadata":   {"source": "arxiv"},
      "trust_tier": "verified"
    }
  ]
}
```

Agents can filter by trust tier:

```python
results = client.query("attention mechanisms")
trusted = [r for r in results if r["trust_tier"] in ("verified", "sovereign")]
```

### Signing an attestation (Python SDK)

```python
from engram.miner.attestation import build_attestation_payload
import bittensor as bt
import requests

wallet = bt.wallet(name="my_wallet")
payload = build_attestation_payload(wallet.hotkey, "my_namespace")
resp = requests.post("http://miner:8091/AttestNamespace", json=payload)
print(resp.json())  # {"ok": true, "trust_tier": "verified", ...}
```

---

## Anti-Spam

### Stake Check

Ingest requests from wallets with less than `MIN_INGEST_STAKE_TAO` (default τ0.001) TAO are rejected with:

```json
{"error": "Insufficient stake: τ0.0000 < τ0.001 minimum required"}
```

The check fails open — if the subtensor connection is unavailable, the request is allowed.

### Rate Limiter

Each hotkey is limited to `RATE_LIMIT_MAX_REQUESTS` (default 100) ingest requests per `RATE_LIMIT_WINDOW_SECS` (default 60 seconds). Excess requests return HTTP 429:

```json
{"error": "Rate limit exceeded: max 100 ingest requests per 60s per hotkey"}
```

---

## Constants

All subnet-wide constants are in `engram/config.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_DIM` | 1536 | Vector dimension (OpenAI text-embedding-3-small) |
| `CANONICAL_MODEL` | `text-embedding-3-small` | Canonical embedding model |
| `CANONICAL_MODEL_VERSION` | `v1` | Model epoch string used in CID generation |
| `REPLICATION_FACTOR` | 3 | Number of miners that store each CID |
| `RECALL_K` | 10 | K for recall@K evaluation |
| `SCORE_ALPHA` | 0.50 | Recall weight |
| `SCORE_BETA` | 0.30 | Latency weight |
| `SCORE_GAMMA` | 0.20 | Proof weight |
| `LATENCY_TARGET_MS` | 100.0 | Latency → 1.0 below this |
| `LATENCY_BASELINE_MS` | 500.0 | Latency → 0.0 above this |
| `CHALLENGE_INTERVAL_SECS` | 300 | Challenge round frequency |
| `CHALLENGE_TIMEOUT_SECS` | 10 | Challenge TTL |
| `CHALLENGE_NONCE_BYTES` | 32 | Nonce size |
| `SLASH_THRESHOLD` | 0.50 | Proof rate below which score → 0 |
| `MIN_INGEST_STAKE_TAO` | 0.001 | Minimum stake to ingest |
| `MAX_TEXT_CHARS` | 8192 | Maximum text length for ingest |
| `MAX_METADATA_BYTES` | 4096 | Maximum metadata size (JSON) |
| `SPEC_VERSION` | 100 | Bumped on any breaking protocol change |
| `TRUST_TIER_SOVEREIGN` | 1000.0 | TAO stake threshold for sovereign tier |
| `TRUST_TIER_VERIFIED` | 100.0 | TAO stake threshold for verified tier |
| `TRUST_TIER_COMMUNITY` | 1.0 | TAO stake threshold for community tier |
| `ATTESTATION_STAKE_REFRESH_SECS` | 600 | How often to refresh owner stake from metagraph |
