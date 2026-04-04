# Engram

**Decentralized Vector Database — Bittensor Subnet**

> IPFS-style content-addressed storage for embeddings. The permanent, open semantic memory layer for AI agents and developers.

---

## What is Engram?

Engram is a Bittensor subnet that gives every embedding a permanent **content identifier (CID)** — the same insight IPFS had for files, applied to semantic knowledge.

- **Store** text or raw embeddings once, retrieve them forever by semantic similarity
- **Content-addressed** — the same knowledge always has the same CID, across every miner
- **Decentralized** — embeddings are replicated across multiple miners (replication factor 3)
- **Verifiable** — storage proofs (HMAC challenge-response) ensure miners actually hold the data

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/Dipraise1/-Engram-.git
cd Engram
pip install -e ".[qdrant]"
```

### 2. Build the Rust core

```bash
pip install maturin
cd engram-core && maturin develop --release && cd ..
```

### 3. Configure

```bash
cp .env.example .env
# Set WALLET_NAME, NETUID, OPENAI_API_KEY (or USE_LOCAL_EMBEDDER=true), etc.
```

### 4. Start Qdrant

```bash
docker run -d -p 6333:6333 qdrant/qdrant
```

### 5. Run a miner

```bash
python neurons/miner.py
```

### 6. Run a validator

```bash
USE_LOCAL_EMBEDDER=true python scripts/generate_ground_truth.py --count 1000
python neurons/validator.py
```

---

## SDK

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

Full reference: [docs/sdk.md](docs/sdk.md)

---

## CLI

```bash
# Ingest text
engram ingest "Some important knowledge"
engram ingest --file corpus.jsonl

# Search
engram query "what is self-attention?"

# Check status
engram status
engram status --live --netuid 42   # live metagraph + miner health
```

Full reference: [docs/cli.md](docs/cli.md)

---

## Scoring

Validators score miners every 120 seconds:

```
composite_score = 0.50 × recall@10
               + 0.30 × latency_score     (1.0 at ≤100ms, 0.0 at ≥500ms)
               + 0.20 × proof_success_rate
```

Weights are set on-chain every 600 seconds, proportional to normalised scores. Miners with proof success rate below 50% receive weight 0.

---

## Architecture

```
Bittensor Chain  ←→  Validator  ←→  Miner (aiohttp JSON)
                                       ├── Qdrant HNSW index
                                       ├── OpenAI / local embedder
                                       └── engram-core (Rust, PyO3)
                                              ├── CID generation (SHA-256)
                                              └── Storage proofs (HMAC)
```

Full design: [docs/architecture.md](docs/architecture.md)

---

## Documentation

| Guide | Description |
|-------|-------------|
| [docs/architecture.md](docs/architecture.md) | System design, data flows, component overview |
| [docs/miner.md](docs/miner.md) | Miner setup, configuration, optimisation, monitoring |
| [docs/validator.md](docs/validator.md) | Validator setup and scoring loop |
| [docs/sdk.md](docs/sdk.md) | Python SDK full reference |
| [docs/cli.md](docs/cli.md) | CLI command reference |
| [docs/protocol.md](docs/protocol.md) | Wire protocol, CID spec, scoring formulas, constants |

---

## Tests

```bash
# Python (55 tests)
pytest tests/ -q

# Rust (9 tests)
cargo test --manifest-path engram-core/Cargo.toml --no-default-features
```

---

## Network

| Property | Value |
|----------|-------|
| Network | Bittensor (TAO) |
| Type | Infrastructure / Storage |
| Status | Testnet |
| Canonical model | `text-embedding-3-small` (v1) |
| Vector index | HNSW via Qdrant |
| Replication factor | 3 |
| Embedding dimension | 1536 |

---

*2026 — Permanent semantic memory for AI.*
