# Engram

**Decentralized Vector Database on Bittensor**

> Permanent, content-addressed semantic memory for AI — no central authority, no single point of failure.

[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Bittensor](https://img.shields.io/badge/bittensor-subnet-orange.svg)](https://bittensor.com)
[![Status](https://img.shields.io/badge/status-testnet-yellow.svg)](https://theengram.space)
[![Docs](https://img.shields.io/badge/docs-theengram.space-blueviolet.svg)](https://theengram.space/docs)

---

## What is Engram?

Engram applies the IPFS insight to AI memory: every piece of knowledge gets a **content identifier (CID)** derived deterministically from its embedding. The same text always maps to the same CID — regardless of which miner stores it.

- **Content-addressed** — `v1::a3f2b1...` uniquely identifies an embedding, not a location
- **Decentralized** — embeddings are replicated across competing miners on Bittensor
- **Incentivized** — miners earn TAO for provably storing and serving vectors
- **Verifiable** — HMAC challenge-response proofs ensure miners actually hold the data

```
         store("The transformer architecture changed everything.")
                              │
                              ▼
              ┌───────────────────────────────┐
              │   CID: v1::a3f2b1c4d5e6f7...  │
              │   Embedding: [0.02, -0.14, ...]│
              │   Stored on: miners 3, 7, 11  │
              └───────────────────────────────┘
                              │
                  query("how does attention work?")
                              │
                              ▼
              ┌───────────────────────────────┐
              │   score: 0.9821  cid: v1::a3f │
              │   score: 0.8744  cid: v1::b2e │
              │   score: 0.8291  cid: v1::c1d │
              └───────────────────────────────┘
```

---

## Quick Start

### Install

```bash
pip install engram-subnet
```

Or from source:

```bash
git clone https://github.com/Dipraise1/-Engram-.git
cd -Engram-
pip install -e .
```

### Configure

```bash
cp .env.example .env
# Edit: WALLET_NAME, NETUID, SUBTENSOR_NETWORK
# Optional: USE_LOCAL_EMBEDDER=true  (no OpenAI key needed)
```

### Python SDK

```python
from engram.sdk import EngramClient

client = EngramClient("http://127.0.0.1:8091")

# Store text — returns a permanent CID
cid = client.ingest("The transformer architecture changed everything.")
print(cid)  # v1::a3f2b1...

# Semantic search
results = client.query("how does attention work?", top_k=5)
for r in results:
    print(f"{r['score']:.4f}  {r['cid']}")

# Batch ingest from JSONL
cids = client.batch_ingest_file("data/corpus.jsonl")
```

### CLI

```bash
engram ingest "Some important knowledge"
engram ingest --file corpus.jsonl
engram ingest --dir ./docs          # recursive directory ingest

engram query "what is self-attention?"

engram status                        # local store info
engram status --live --netuid 42     # live metagraph + miner health
```

---

## Framework Integrations

```python
# LangChain
from engram.sdk.langchain import EngramVectorStore
store = EngramVectorStore(miner_url="http://127.0.0.1:8091", embeddings=your_embeddings)
retriever = store.as_retriever(search_kwargs={"k": 5})

# LlamaIndex
from engram.sdk.llama_index import EngramVectorStore
store = EngramVectorStore(miner_url="http://127.0.0.1:8091")
index = VectorStoreIndex.from_documents(
    documents,
    storage_context=StorageContext.from_defaults(vector_store=store)
)
```

---

## Running a Miner

```bash
# Create wallet
btcli wallet new_coldkey --wallet.name engram
btcli wallet new_hotkey --wallet.name engram --wallet.hotkey miner

# Register on subnet
btcli subnet register --netuid 42 --wallet.name engram --wallet.hotkey miner

# Start
python neurons/miner.py --wallet.name engram --wallet.hotkey miner --netuid 42
```

Full setup: [docs/miner.md](docs/miner.md)

---

## Running a Validator

```bash
btcli subnet register --netuid 42 --wallet.name engram --wallet.hotkey validator
python neurons/validator.py --wallet.name engram --wallet.hotkey validator --netuid 42
```

Full setup: [docs/validator.md](docs/validator.md)

---

## Scoring

Validators score miners every 120 seconds:

```
composite_score = 0.50 × recall@10
               + 0.30 × latency_score     (1.0 at ≤100ms, 0.0 at ≥500ms)
               + 0.20 × proof_success_rate
```

Miners with proof success rate below 50% receive weight 0.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       Bittensor Chain                        │
│               (metagraph · weight setting · TAO)             │
└─────────────────────┬──────────────────────┬─────────────────┘
                      │                      │
              ┌───────▼──────┐    ┌──────────▼──────┐
              │  Validator   │    │      Miner       │
              │              │    │                  │
              │ • challenge  │───▶│ • FAISS index    │
              │ • score      │    │ • embedder       │
              │ • set weights│◀───│ • proof service  │
              └──────────────┘    └──────────┬───────┘
                                             │
                                   ┌─────────▼────────┐
                                   │   engram-core     │
                                   │   (Rust / PyO3)   │
                                   │ • CID generation  │
                                   │ • HMAC proofs     │
                                   └──────────────────┘
```

---

## Repository Structure

```
engram/
├── engram/              # Python package
│   ├── miner/           # Ingest, query, embedder, store, rate limiter
│   ├── validator/       # Scoring, challenge, weight setting
│   ├── sdk/             # Client, LangChain, LlamaIndex adapters
│   └── protocol.py      # Synapse types (IngestSynapse, QuerySynapse)
├── engram-core/         # Rust core — CID generation + storage proofs
├── engram-web/          # Next.js frontend (theengram.space)
├── neurons/             # miner.py, validator.py entry points
├── scripts/             # Demo, ground truth generation, utilities
├── tests/               # pytest suite
└── docs/                # Architecture, SDK, CLI, protocol reference
```

---

## Documentation

| Guide | Description |
|-------|-------------|
| [docs/architecture.md](docs/architecture.md) | System design, data flows, component overview |
| [docs/miner.md](docs/miner.md) | Miner setup, configuration, optimization |
| [docs/validator.md](docs/validator.md) | Validator setup and scoring loop |
| [docs/sdk.md](docs/sdk.md) | Python SDK full reference |
| [docs/cli.md](docs/cli.md) | CLI command reference |
| [docs/protocol.md](docs/protocol.md) | Wire protocol, CID spec, scoring formulas |

Full web docs: **[theengram.space/docs](https://theengram.space/docs)**

---

## Tests

```bash
pytest tests/ -q
cargo test --manifest-path engram-core/Cargo.toml --no-default-features
```

---

## Network

| Property | Value |
|----------|-------|
| Network | Bittensor (TAO) |
| Type | Infrastructure / Storage |
| Status | Testnet |
| Subnet UID | 42 (testnet) |
| Canonical embedding model | `text-embedding-3-small` (1536d) |
| Vector index | FAISS (IVF-flat) |
| Proof type | HMAC-SHA256 challenge-response |

---

## Links

- **Website** — [theengram.space](https://theengram.space)
- **Docs** — [theengram.space/docs](https://theengram.space/docs)
- **Dashboard** — [theengram.space/dashboard](https://theengram.space/dashboard)
- **API** — [api.theengram.space/health](https://api.theengram.space/health)

---

*2026 — Permanent semantic memory for AI.*
