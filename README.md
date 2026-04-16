# Engram

**Decentralized AI Memory Layer on Bittensor**

> Permanent, content-addressed semantic memory for AI — store text, images, and PDFs with cryptographic proofs. No central authority, no AWS, no single point of failure.

[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Bittensor](https://img.shields.io/badge/bittensor-subnet%20450-orange.svg)](https://bittensor.com)
[![Status](https://img.shields.io/badge/status-testnet%20live-green.svg)](https://theengram.space)
[![Dashboard](https://img.shields.io/badge/dashboard-theengram.space-blueviolet.svg)](https://theengram.space)

---

## What is Engram?

Engram is a Bittensor subnet that turns text, images, and documents into **permanently stored, content-addressed memories**. Every piece of knowledge gets a deterministic CID derived from its embedding — the same content always maps to the same identifier, regardless of which miner stores it.

- **Content-addressed** — `v1::a3f2b1...` uniquely identifies an embedding, not a location
- **Decentralized** — replicated across competing miners on Bittensor subnet 450
- **Permanent** — binary files (images, PDFs) pinned to Arweave; text indexed in FAISS HNSW
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

## Live Network

| Property | Value |
|----------|-------|
| Network | Bittensor Testnet |
| Subnet UID | **450** |
| Embedding model | `all-MiniLM-L6-v2` (384d, local) |
| Vector index | FAISS HNSW |
| Proof type | HMAC-SHA256 challenge-response |
| Blob storage | Arweave (pay-once permanent) |
| Dashboard | [theengram.space](https://theengram.space) |
| Playground | [theengram.space/playground](https://theengram.space/playground) |

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

### Python SDK

```python
from engram.sdk import EngramClient

client = EngramClient("http://72.62.2.34:8091")

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

engram query "what is self-attention?"

engram status                        # local store info
engram status --live --netuid 450    # live metagraph + miner health
```

---

## Storing Files (Playground)

Open [theengram.space/playground](https://theengram.space/playground) to store content from your browser — no wallet or API key needed:

| Tab | What happens |
|-----|-------------|
| **Text** | Embedded with all-MiniLM-L6-v2, stored on miners |
| **Image** | Described by Grok Vision, uploaded to Arweave, embedding stored on miners |
| **PDF** | Text extracted, uploaded to Arweave, embedding stored on miners |

Every stored item gets a CID you can share. Retrieve it at `theengram.space/cid/<YOUR_CID>`.

### Two-CID Architecture

Images and PDFs get **two identifiers**:

```
engram_cid   = v1::sha256(embedding + metadata)   ← semantic address for search
content_cid  = sha256:sha256(raw_bytes)            ← content address for retrieval
arweave_tx   = <Arweave transaction ID>            ← permanent off-chain blob
```

---

## Framework Integrations

```python
# LangChain
from engram.sdk.langchain import EngramVectorStore
store = EngramVectorStore(miner_url="http://72.62.2.34:8091", embeddings=your_embeddings)
retriever = store.as_retriever(search_kwargs={"k": 5})

# LlamaIndex
from engram.sdk.llama_index import EngramVectorStore
store = EngramVectorStore(miner_url="http://72.62.2.34:8091")
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

# Register on subnet (testnet)
btcli subnet register --netuid 450 --wallet.name engram --wallet.hotkey miner --subtensor.network test

# Configure
cp .env.example .env.miner
# Set: WALLET_NAME, WALLET_HOTKEY, NETUID=450, SUBTENSOR_NETWORK=test

# Start
ENV_FILE=.env.miner python neurons/miner.py
```

The miner starts even if the testnet RPC is temporarily unavailable — it retries the chain connection in the background and runs chain-less until it reconnects.

Full guide: [docs/miner.md](docs/miner.md)

---

## Running a Validator

```bash
btcli subnet register --netuid 450 --wallet.name engram --wallet.hotkey validator --subtensor.network test

cp .env.example .env.validator
# Set: WALLET_NAME, WALLET_HOTKEY, NETUID=450, SUBTENSOR_NETWORK=test

ENV_FILE=.env.validator python neurons/validator.py
```

Full guide: [docs/validator.md](docs/validator.md)

---

## Scoring

```
composite_score = 0.50 × recall@10
               + 0.30 × latency_score     (1.0 at ≤100ms, 0.0 at ≥500ms)
               + 0.20 × proof_success_rate
```

Validators score miners every 120 seconds. Miners with proof success rate below 50% receive weight 0.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Bittensor Chain                           │
│                (metagraph · weight setting · TAO)                │
└─────────────────────┬──────────────────────┬─────────────────────┘
                      │                      │
              ┌───────▼──────┐    ┌──────────▼──────┐
              │  Validator   │    │      Miner       │
              │              │    │                  │
              │ • recall@K   │───▶│ • FAISS HNSW     │
              │ • challenge  │    │ • embedder       │
              │ • set weights│◀───│ • proof service  │
              └──────────────┘    └──────────┬───────┘
                                             │
                                   ┌─────────▼────────┐
                                   │   engram-core     │
                                   │   (Rust / PyO3)   │
                                   │ • CID generation  │
                                   │ • HMAC proofs     │
                                   └──────────────────┘

              ┌──────────────────────────────────────┐
              │          engram-web (Next.js)         │
              │   playground · memory · dashboard     │
              │            theengram.space            │
              └──────────────┬───────────────────────┘
                             │  images / PDFs
                             ▼
              ┌──────────────────────────────────────┐
              │              Arweave                  │
              │     permanent blob storage            │
              │    pay-once · publicly verifiable     │
              └──────────────────────────────────────┘
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
│   ├── app/playground/  # Text / Image / PDF ingest UI
│   ├── app/memory/      # Memory search + AI chat
│   ├── app/cid/[id]/    # CID lookup + Arweave proof view
│   ├── app/api/         # Next.js API routes → miner proxy
│   └── lib/arweave.ts   # Arweave upload utility
├── neurons/             # miner.py, validator.py entry points
├── scripts/             # Setup, seeding, VPS utilities
├── tests/               # pytest suite
└── docs/                # Architecture, SDK, CLI, protocol reference
```

---

## Documentation

| Guide | Description |
|-------|-------------|
| [docs/architecture.md](docs/architecture.md) | System design, data flows, Arweave integration |
| [docs/miner.md](docs/miner.md) | Miner setup, configuration, systemd |
| [docs/validator.md](docs/validator.md) | Validator setup and scoring loop |
| [docs/sdk.md](docs/sdk.md) | Python SDK full reference |
| [docs/cli.md](docs/cli.md) | CLI command reference |
| [docs/protocol.md](docs/protocol.md) | Wire protocol, CID spec, scoring formulas |

---

## Tests

```bash
pytest tests/ -q
cargo test --manifest-path engram-core/Cargo.toml --no-default-features
```

---

## Links

- **Website** — [theengram.space](https://theengram.space)
- **Playground** — [theengram.space/playground](https://theengram.space/playground)
- **Dashboard** — [theengram.space/dashboard](https://theengram.space/dashboard)
- **GitHub** — [github.com/Dipraise1/-Engram-](https://github.com/Dipraise1/-Engram-)
- **Miner health** — `http://72.62.2.34:8091/health`

---

*2026 — Permanent semantic memory for AI.*
