# Architecture

Engram is a Bittensor subnet that turns any text or embedding into a permanent, content-addressed record stored across a decentralized network of miners.

---

## System Overview

```
┌─────────────────────────────────────────────────────┐
│                   Bittensor Chain                    │
│   metagraph · weights · registration · emissions     │
└──────────────┬──────────────────────┬───────────────┘
               │                      │
    ┌──────────▼──────────┐  ┌────────▼──────────┐
    │     Validator        │  │       Miner        │
    │  ─────────────────  │  │  ───────────────  │
    │  scorer.py           │  │  embedder.py       │
    │  challenge.py        │  │  ingest.py         │
    │  ground_truth.py     │  │  query.py          │
    │  reward.py           │  │  store.py          │
    │  (sets weights)      │  │  metrics.py        │
    └────────┬─────────────┘  └────────┬──────────┘
             │  HTTP (JSON)             │
             └──────────────────────────┘
                        │
             ┌──────────▼──────────┐
             │    engram-core      │  ← Rust (PyO3)
             │  ─────────────────  │
             │  CID generation     │
             │  Storage proofs     │
             └──────────┬──────────┘
                        │
             ┌──────────▼──────────┐
             │   Qdrant / FAISS    │  ← Vector store
             │   HNSW index        │
             └─────────────────────┘
```

---

## Components

### Miner

The miner runs an **aiohttp JSON HTTP server** (default port `8091`) that exposes three endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/IngestSynapse` | POST | Accept text or embedding, store it, return CID |
| `/QuerySynapse` | POST | ANN search, return top-K results |
| `/ChallengeSynapse` | POST | Storage proof challenge-response |
| `/health` | GET | Liveness probe |
| `/metrics` | GET | Prometheus metrics |

On startup the miner:
1. Connects to subtensor and loads the metagraph
2. Initialises the vector store (Qdrant or FAISS)
3. Loads the sentence embedder (OpenAI or local)
4. Bootstraps the DHT routing table from metagraph axons
5. Registers its axon on-chain via `subtensor.serve_axon()`
6. Re-syncs the metagraph every 60 seconds in the background

### Validator

The validator runs a scoring loop with three independent cadences:

| Cadence | Action |
|---------|--------|
| Every 120s | Scoring round — sample 5 ground truth entries, query all miners, compute recall@K and latency scores |
| Every 300s | Challenge round — pick a random CID, issue HMAC challenge to all miners, record pass/fail |
| Every 600s | Weight round — compute composite scores, normalise, call `set_weights` on-chain |

### Rust Core (`engram-core`)

A PyO3 extension built with maturin. Python falls back to a pure-Python equivalent if the wheel isn't installed.

| Function | Description |
|----------|-------------|
| `generate_cid(embedding, metadata, version)` | SHA-256 content identifier |
| `generate_challenge(cid)` | Random 32-byte nonce + TTL |
| `verify_response(challenge, embedding_hash, proof, expected_embedding)` | HMAC proof verification |

### DHT Router

Kademlia-inspired routing for CID → miner assignment. The miner with the closest XOR distance to the CID's hash becomes the **primary** replica; the next two closest become secondaries (replication factor = 3).

The `DHTRouter` is synced from the metagraph on startup and after each 60-second refresh, so the topology tracks miner churn automatically.

### Replication Manager

Tracks which miners have confirmed storage of each CID. A CID can be in one of three states:

| Status | Meaning |
|--------|---------|
| `HEALTHY` | All 3 replicas confirmed via proof challenge |
| `DEGRADED` | 1–2 replicas confirmed (some miners offline or failing proofs) |
| `LOST` | 0 confirmed replicas |

Miners that come back online can be targeted for repair by calling `ReplicationManager.get_repair_targets()`.

---

## Data Flow — Ingest

```
Client                   Miner                    Chain
  │                        │                        │
  │── POST /IngestSynapse ──►                        │
  │   {text, metadata}      │                        │
  │                    embed(text) → float32[1536]   │
  │                    cid = SHA-256(emb ‖ meta ‖ v) │
  │                    store.upsert(cid, embedding)  │
  │                    replication_mgr.register(cid) │
  │◄── {cid}                │                        │
```

---

## Data Flow — Query

```
Validator               Miner
  │                       │
  │── POST /QuerySynapse ──►
  │   {query_vector, k}   │
  │                  store.search(vec, k) → HNSW
  │◄── {results: [{cid, score, metadata}]}
```

---

## Data Flow — Storage Proof

```
Validator                          Miner
  │                                  │
  │── POST /ChallengeSynapse ─────────►
  │   {cid, nonce_hex, expires_at}   │
  │                            record = store.get(cid)
  │                            emb_hash = SHA-256(emb bytes)
  │                            proof = HMAC-SHA256(nonce, emb_hash)
  │◄── {embedding_hash, proof}        │
  │                                  │
  verify_response(challenge, hash, proof, expected_emb)
  → pass/fail → update score
```

---

## CID Format

```
v1::<sha256_hex>
```

Generated deterministically from:
1. Little-endian IEEE-754 float32 bytes of the embedding
2. Sorted `key=value` metadata pairs
3. Model version string (e.g. `v1`)

The same embedding + metadata always produces the same CID. Changing any bit of the embedding changes the CID.

---

## Vector Store Backends

| Backend | Best for | Notes |
|---------|----------|-------|
| **Qdrant** | Production, >10k vectors | Rust-native HNSW, persistent, high recall |
| **FAISS** | Development, testing | In-process, no extra service required; recall degrades in small growing indices |

Switch with `VECTOR_STORE_BACKEND=qdrant` (default `faiss`).

---

## Scoring

```
composite_score = 0.50 × recall@10
               + 0.30 × latency_score
               + 0.20 × proof_success_rate
```

On-chain weights are set proportional to normalised composite scores. See [protocol.md](protocol.md) for the full scoring specification.
