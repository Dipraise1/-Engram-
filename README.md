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
- **Permanent** — binary files (images, PDFs) pinned to Arweave across the full stack (SDK, miner, web)
- **Private** — X25519 hybrid encryption with differential privacy noise on stored embeddings
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
| Vector index | Qdrant (persistent WAL) |
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

client = EngramClient("https://api.theengram.space")

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

### Arweave Integration (full stack)

Arweave storage is now wired through the entire subnet — not just the web frontend.
Set `ARWEAVE_KEY` (JWK JSON) in the miner or SDK environment and raw media is automatically
uploaded before vectorization. The `arweave_tx_id` and `arweave_url` are stored in vector metadata.

```python
import os
os.environ["ARWEAVE_KEY"] = '{"kty":"RSA",...}'   # your JWK wallet

client = EngramClient("https://api.theengram.space")

# Raw image bytes uploaded to Arweave, description embedded on miner
result = client.ingest_image("photo.jpg", xai_api_key="xai-...")
print(result["arweave_url"])    # https://arweave.net/<tx_id>

# PDF bytes archived on Arweave, text embedded on miner
result = client.ingest_pdf("paper.pdf")
print(result["arweave_tx_id"])

# Page HTML archived on Arweave, text extracted and embedded
result = client.ingest_url("https://arxiv.org/abs/1706.03762")
```

For private namespaces, raw bytes are **encrypted with your X25519 public key before upload** so
Arweave gateway operators cannot read the content.

### Privacy & Security

| Protection | Mechanism | ATLAS | Status |
|---|---|---|---|
| Private namespace encryption | X25519 ECDH + HKDF + AES-256-GCM per message | — | ✅ |
| Vector inversion resistance | Gaussian DP noise on stored embeddings (ε=3.0) | AML.T0024 | ✅ |
| Encrypted media on Arweave | `encrypt_raw()` before upload for private clients | AML.T0035 | ✅ |
| Namespace auth — no key on wire | sr25519 signed challenge replaces `namespace_key` | AML.T0043 | ✅ |
| Flag-stripping downgrade | `namespace` + `hotkey` covered by sig — stripping invalidates it | AML.T0043 | ✅ |
| TLS on miner endpoints | `https://api.theengram.space` terminates TLS before port 8091 | passive sniff | ✅ |
| Namespace trust tiers | sr25519 attestation + on-chain stake tiers | AML.T0010 | ✅ |
| Anti-sybil | Stake-weighted trust + slash threshold | AML.T0016 | ✅ |
| Compromised miner reads queries | Threshold decryption (K-of-N) | AML.T0010 | 🔲 planned |
| Timing / access-pattern leak | Uniform response padding | AML.T0036 | 🔲 planned |

**Namespace auth** — when a `keypair` is set on the client, the raw key never leaves the machine.
The client signs `engram-ns:{namespace}:{timestamp_ms}` with its sr25519 hotkey; the miner
verifies the signature and stores the hotkey as the namespace owner. Legacy `namespace_key`
still works for backward compatibility.

```python
# Secure namespace auth (keypair-based)
import bittensor as bt
wallet = bt.wallet(name="my_wallet")
client = EngramClient("https://api.theengram.space", keypair=wallet.hotkey, namespace="my-ns")
cid = client.ingest("private data")   # sig challenge sent — key never on wire

# Legacy (still works, deprecated)
client = EngramClient("https://api.theengram.space", namespace="my-ns", namespace_key="secret")
```

Configure DP noise: `DP_EPSILON=3.0` (default). Set to `none` to disable.  
SDK clients should use `https://api.theengram.space` as `MINER_API_URL` to get TLS.

---

## Framework Integrations

```python
# LangChain
from engram.sdk.langchain import EngramVectorStore
store = EngramVectorStore(miner_url="https://api.theengram.space", embeddings=your_embeddings)
retriever = store.as_retriever(search_kwargs={"k": 5})

# LlamaIndex
from engram.sdk.llama_index import EngramVectorStore
store = EngramVectorStore(miner_url="https://api.theengram.space")
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

**Optional env vars:**

| Variable | Default | Description |
|---|---|---|
| `ARWEAVE_KEY` | — | JWK wallet JSON; enables Arweave media archival |
| `DP_EPSILON` | `3.0` | DP noise for private namespace embeddings (`none` to disable) |
| `REQUIRE_HOTKEY_SIG` | `false` | Reject unsigned requests |

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
│   ├── miner/           # Ingest (+ DP noise), query, embedder, store, rate limiter
│   ├── validator/       # Scoring, challenge, weight setting
│   ├── sdk/             # Client (+ Arweave), LangChain, LlamaIndex, encryption
│   ├── storage/         # arweave.py — permanent media upload (Python layer)
│   └── protocol.py      # Synapse types (IngestSynapse, QuerySynapse)
├── engram-core/         # Rust core — CID generation + storage proofs
├── engram-web/          # Next.js frontend (theengram.space, Vercel)
│   ├── app/playground/  # Text / Image / PDF ingest UI
│   ├── app/memory/      # Memory search + AI chat
│   ├── app/cid/[id]/    # CID lookup + Arweave proof view
│   ├── app/api/         # Next.js API routes → miner proxy
│   └── lib/arweave.ts   # Arweave upload utility (web layer)
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
