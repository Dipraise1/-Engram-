# Architecture

Engram is a Bittensor subnet that turns text, images, and documents into permanent, content-addressed records stored across a decentralized network of miners — with binary blobs pinned to Arweave.

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
             │   FAISS HNSW index  │  ← Vector store
             └─────────────────────┘

             ┌──────────────────────────────────────┐
             │          engram-web (Next.js)         │
             │   playground · memory · dashboard     │
             └──────────────┬───────────────────────┘
                            │  images / PDFs
                            ▼
             ┌──────────────────────────────────────┐
             │              Arweave                  │
             │  pay-once permanent blob storage      │
             └──────────────────────────────────────┘
```

---

## Components

### Miner

The miner runs an **aiohttp JSON HTTP server** (default port `8091`) that exposes:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/IngestSynapse` | POST | Accept text or embedding, store it, return CID |
| `/QuerySynapse` | POST | ANN search, return top-K results |
| `/ChallengeSynapse` | POST | Storage proof challenge-response |
| `/health` | GET | Liveness probe |
| `/stats` | GET | Metrics: vectors, peers, scores, uptime |

On startup the miner:
1. Attempts to connect to subtensor — retries up to 5 times with 10s backoff, runs chain-less if all fail
2. Initialises the FAISS HNSW vector store
3. Loads the local `all-MiniLM-L6-v2` embedder (384d, no API key required)
4. Bootstraps the DHT routing table from metagraph axons
5. Registers its axon on-chain via `subtensor.serve_axon()`
6. Re-syncs the metagraph every 5 minutes in a thread pool (non-blocking)

### Validator

The validator runs a scoring loop with three independent cadences:

| Cadence | Action |
|---------|--------|
| Every 120s | Scoring — sample 5 ground truth entries, query all miners, compute recall@K and latency |
| Every 300s | Challenge — pick a random CID, issue HMAC challenge to all miners, record pass/fail |
| Every 600s | Weights — compute composite scores, normalise, call `set_weights` on-chain |

The validator retries the subtensor connection on startup (same 5-attempt pattern as the miner) and reconnects automatically if the chain becomes temporarily unreachable mid-loop.

### Rust Core (`engram-core`)

A PyO3 extension built with maturin. Python falls back to pure-Python equivalents if the wheel is not installed.

| Function | Description |
|----------|-------------|
| `generate_cid(embedding, metadata, version)` | SHA-256 content identifier |
| `generate_challenge(cid)` | Random 32-byte nonce + TTL |
| `verify_response(challenge, embedding_hash, proof, expected_embedding)` | HMAC proof verification |

### DHT Router

Kademlia-inspired routing for CID → miner assignment. The miner with the closest XOR distance to the CID's hash is the **primary** replica; the next two closest become secondaries (replication factor = 3).

Synced from the metagraph on startup and after each refresh cycle.

### Replication Manager

Tracks which miners have confirmed storage of each CID:

| Status | Meaning |
|--------|---------|
| `HEALTHY` | All 3 replicas confirmed via proof challenge |
| `DEGRADED` | 1–2 replicas confirmed |
| `LOST` | 0 confirmed replicas |

### Arweave Integration

Binary files (images and PDFs) uploaded through the playground are stored permanently on Arweave before being indexed in Engram. This creates two complementary identifiers:

```
engram_cid   = v1::sha256(embedding + metadata)   ← semantic address for search
content_cid  = sha256:sha256(raw_bytes)            ← content address for retrieval
arweave_tx   = <43-char base64url ID>              ← permanent publicly accessible blob
```

The Arweave upload is **non-fatal** — if it fails (e.g. wallet not funded), the text embedding is still stored in Engram and the CID remains valid for semantic search.

For images, [Grok Vision](https://console.x.ai) generates a text description that becomes the embedding input. The description is stored as metadata so users can read it back on the CID page.

---

## Data Flow — Text Ingest

```
Client                   Miner
  │                        │
  │── POST /IngestSynapse ──►
  │   {text, metadata}      │
  │                    embed(text) → float32[384]
  │                    cid = SHA-256(emb ‖ meta ‖ v)
  │                    store.upsert(cid, embedding)
  │◄── {cid}                │
```

## Data Flow — Image Ingest (via Playground)

```
Browser          Next.js API            Grok Vision       Arweave        Miner
  │                  │                      │                │              │
  │── POST file ──►  │                      │                │              │
  │               ├─ describe(image) ────►  │                │              │
  │               ├─ upload(bytes) ────────────────────────► │              │
  │               │◄── description ──────── │                │              │
  │               │◄── tx_id ──────────────────────────────  │              │
  │               ├─ POST /IngestSynapse {text=description, metadata} ─────► │
  │               │◄── {cid} ──────────────────────────────────────────────  │
  │◄── {cid, arweave_tx_id, content_cid}   │
```

## Data Flow — Storage Proof

```
Validator                          Miner
  │                                  │
  │── POST /ChallengeSynapse ─────────►
  │   {cid, nonce_hex, expires_at}   │
  │                            emb_hash = SHA-256(embedding bytes)
  │                            proof   = HMAC-SHA256(nonce, emb_hash)
  │◄── {embedding_hash, proof}        │
  │                                  │
  verify_response(challenge, hash, proof, expected_emb)
  → pass/fail → update proof_rate
```

---

## CID Format

```
v1::<sha256_hex>
```

Generated deterministically from:
1. Little-endian IEEE-754 float32 bytes of the embedding
2. Sorted `key=value` metadata pairs
3. Model version string (`v1`)

The same embedding + metadata always produces the same CID. Changing any bit changes the CID.

---

## Scoring

```
composite_score = 0.50 × recall@10
               + 0.30 × latency_score
               + 0.20 × proof_success_rate
```

Where:
- `latency_score = 1.0` at ≤100ms, `0.0` at ≥500ms, linear between
- `proof_success_rate` = rolling fraction of HMAC challenges passed
- Miners below 50% proof rate are slashed to weight 0

On-chain weights are set proportional to normalised composite scores. See [protocol.md](protocol.md) for the full specification.
