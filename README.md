# Engram

**Decentralized Vector Database Subnet on Bittensor**

> IPFS-style content-addressed storage for embeddings — the permanent, open semantic memory layer for AI agents and developers.

---

## What is Engram?

Engram is a Bittensor subnet that gives every embedding a permanent content identifier (CID) — the same insight IPFS had for files, applied to semantic knowledge.

- **Miners** store and serve embedding vectors (via Qdrant, a Rust-native vector DB)
- **Validators** score miners on recall@K, query latency, and storage proof success rate
- **Anyone** can ingest text or raw embeddings and retrieve them by semantic similarity — forever

---

## Architecture

```
Python neurons (Bittensor protocol)
         ↕
Rust core (engram-core via PyO3)
  ├── CID generation   — SHA-256 content addressing
  └── Storage proofs   — HMAC challenge-response

         ↕
Qdrant vector store (Rust binary)
  └── HNSW index — fast approximate nearest-neighbor
```

---

## Project Structure

```
engram/
├── engram-core/          # Rust — CID + storage proofs (PyO3)
│   └── src/
│       ├── lib.rs        # PyO3 module exports
│       ├── cid.rs        # Content identifier generation
│       └── proof.rs      # Storage challenge-response
├── engram/               # Python package
│   ├── protocol.py       # Bittensor Synapse definitions
│   ├── config.py         # Subnet-wide constants
│   ├── cid.py            # Python CID fallback
│   ├── miner/
│   │   ├── store.py      # Qdrant + FAISS vector store abstraction
│   │   ├── embedder.py   # OpenAI / sentence-transformers
│   │   ├── ingest.py     # IngestSynapse handler
│   │   └── query.py      # QuerySynapse handler
│   └── validator/
│       ├── scorer.py     # recall@K, latency, proof scoring
│       ├── challenge.py  # Storage proof dispatcher
│       ├── ground_truth.py
│       └── reward.py     # Weight-setting logic
├── neurons/
│   ├── miner.py          # Miner neuron entry point
│   └── validator.py      # Validator neuron entry point
├── sdk/
│   └── client.py         # Python SDK
├── tests/
├── docker/
├── scripts/
│   └── seed_corpus.py    # Bootstrap corpus ingestion
└── docker-compose.yml
```

---

## Quickstart

### 1. Build the Rust core

```bash
pip install maturin
cd engram-core && maturin develop --release
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY, WALLET_NAME, NETUID, etc.
```

### 4. Start Qdrant

```bash
docker run -p 6333:6333 qdrant/qdrant
```

### 5. Run a miner

```bash
python neurons/miner.py
```

### 6. Run a validator

```bash
python neurons/validator.py
```

---

## SDK Usage

```python
import bittensor as bt
from engram.sdk.client import EngramClient

wallet = bt.wallet(name="my_wallet")
client = EngramClient(wallet=wallet, netuid=99, network="finney")

# Store text
cid = client.ingest("The attention mechanism in transformers...")

# Semantic search
results = client.query("how does self-attention work?", top_k=10)
for r in results:
    print(r["score"], r["metadata"])
```

---

## Scoring Formula

```
score = 0.50 × recall@10  +  0.30 × latency_score  +  0.20 × proof_success_rate
```

Miners earn TAO by serving fast, accurate queries and proving they hold the data they claim to store.

---

## Miner Incentive Guide

### How scoring works

Every ~60s validators run a full scoring round against each registered miner:

| Component | Weight | How it's measured |
|-----------|--------|-------------------|
| `recall@10` | **50%** | Validator ingests N known embeddings, then queries with the same vectors and checks how many of the expected CIDs appear in the top-10 results |
| `latency_score` | **30%** | `max(0, 1 − latency_ms / 1000)` — a 100ms response scores 0.90; 500ms scores 0.50; >1s scores 0 |
| `proof_success_rate` | **20%** | Validator issues HMAC challenge-response challenges for stored CIDs; fraction that pass within TTL |

Final weights on-chain are set proportional to composite scores across all miners in the subnet.

### What to optimize

**1. Recall@10 (highest impact)**

- Use **Qdrant** (`VECTOR_STORE_BACKEND=qdrant`) — its HNSW index scales to millions of vectors while maintaining >99% recall, whereas FAISS in small indices can miss recently added nodes
- Keep `hnsw_ef_search` ≥ 128 (default in `store.py`)
- Don't prune or evict vectors — every stored CID is a potential query target

**2. Query latency**

- Run on a machine with ≥4 CPU cores; Qdrant's HNSW search is CPU-bound
- Keep Qdrant on localhost (same machine as miner) to avoid network RTT
- Set `MINER_PORT` to avoid port contention; don't run other heavy processes alongside the miner
- MPS/CUDA for local embedder (`USE_LOCAL_EMBEDDER=true`) cuts embed time but OpenAI API (default) batches faster for bulk ingest

**3. Proof success rate**

- The miner must be reachable at `EXTERNAL_IP:MINER_PORT` at all times — use a static IP or dynamic DNS
- Challenges expire after their TTL (typically 30s); ensure miner process doesn't stall on GC or I/O
- The HMAC proof is computed over the stored embedding — never delete data after ingesting it

### Recommended hardware

| Tier | Specs | Expected score |
|------|-------|----------------|
| Minimum | 2 vCPU, 4 GB RAM, 20 GB SSD | ~0.70 |
| Recommended | 4 vCPU, 16 GB RAM, 100 GB SSD | ~0.88 |
| High-performance | 8 vCPU, 32 GB RAM, NVMe SSD | ~0.95+ |

### Environment variables

```bash
# Core
WALLET_NAME=default
WALLET_HOTKEY=default
SUBTENSOR_NETWORK=finney     # or ws://your-node:9944
NETUID=<subnet-uid>
MINER_PORT=8091
EXTERNAL_IP=<your-public-ip>

# Storage
VECTOR_STORE_BACKEND=qdrant  # or faiss
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Embedder
USE_LOCAL_EMBEDDER=false      # true = sentence-transformers (offline)
OPENAI_API_KEY=sk-...         # required if USE_LOCAL_EMBEDDER=false

# Rate limiting (anti-spam)
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_WINDOW_SECS=60
```

### Monitoring

The miner exposes a Prometheus metrics endpoint at `GET /metrics`:

```
engram_ingest_total{status="ok|error|rate_limited|low_stake"}
engram_query_total{status="ok|error"}
engram_ingest_duration_ms  (histogram)
engram_query_duration_ms   (histogram)
engram_vectors_stored      (gauge)
engram_proof_total{result="pass|fail|expired"}
engram_proof_success_rate  (gauge, 0–1)
engram_score               (gauge — last score from validator)
engram_peers_online        (gauge — DHT peer count)
```

Add `http://<miner-ip>:8091/metrics` to your Prometheus scrape config, or just `curl` it directly.

---

## Running Tests

```bash
# Python tests
pytest tests/

# Rust tests
cargo test -p engram-core
```

---

## Network

| Property | Value |
|----------|-------|
| Network | Bittensor (TAO) |
| Type | Infrastructure / Storage |
| Status | Proposal → Testnet |
| Canonical model | text-embedding-3-small (v1) |
| Vector index | HNSW via Qdrant |
| Replication | 3× (Phase 1) |

---

*2026 — The idea is yours. Let's build it.*
