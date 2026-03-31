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
