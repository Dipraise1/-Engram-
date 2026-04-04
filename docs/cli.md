# CLI Reference

The `engram` CLI provides a local interface for ingesting text, querying the store, and checking subnet status.

---

## Installation

```bash
pip install -e .
engram --help
```

The CLI defaults to a **local FAISS store** and **local sentence-transformers embedder** (`USE_LOCAL_EMBEDDER=true`). No OpenAI key required.

Configuration is loaded from `.env` in the working directory.

---

## Commands

### `engram ingest`

Embed and store text in the local store.

```bash
engram ingest "The transformer architecture changed everything."
```

```bash
# With metadata
engram ingest "BERT uses bidirectional representations." --meta '{"source":"arxiv"}'

# From a plain text file (one entry per line)
engram ingest --file docs/corpus.txt

# From a JSONL file
engram ingest --file data/corpus.jsonl

# Custom source label
engram ingest "My note" --source "personal-notes"
```

**Arguments:**

| Arg / Flag | Description |
|------------|-------------|
| `TEXT` | Text to embed and store (positional) |
| `--file, -f PATH` | Path to a `.txt` or `.jsonl` file to ingest |
| `--meta, -m JSON` | JSON metadata string (default `{}`) |
| `--source, -s STR` | Source label added to metadata (default `"cli"`) |

**JSONL format** (for `--file`): each line must be a JSON object with a `"text"` key and optional `"metadata"` dict.

**Output:**

```
┌──────────────────────────────┬─────────────────────────────────────────────────────┬────┐
│ CID                          │ Text                                                │ ms │
├──────────────────────────────┼─────────────────────────────────────────────────────┼────┤
│ a3f2b1...4e9c12              │ The transformer architecture changed everything.    │ 42 │
└──────────────────────────────┴─────────────────────────────────────────────────────┴────┘

✓ 1 ingested
```

The FAISS index is saved automatically after each ingest session.

---

### `engram query`

Semantic search over the local store.

```bash
engram query "how does self-attention work?"
```

```bash
# More results
engram query "neural network training" --top-k 10

# Show metadata alongside results
engram query "vector databases" --meta
```

**Arguments:**

| Arg / Flag | Description |
|------------|-------------|
| `TEXT` | Search query (required) |
| `--top-k, -k INT` | Number of results (default 5) |
| `--meta` | Show metadata column in results |

**Output:**

```
Query: how does self-attention work?
5 results in 12ms

┌───┬────────┬──────────────────┬──────────────────────────────┐
│ # │  Score │ CID              │ Metadata                     │
├───┼────────┼──────────────────┼──────────────────────────────┤
│ 1 │ 0.9821 │ a3f2b1...4e9c12  │ {"source": "arxiv"}          │
│ 2 │ 0.9743 │ b1c3d4...7f2a01  │ {"source": "cli"}            │
│ 3 │ 0.9512 │ c2e5f6...3d8b22  │ {}                           │
└───┴────────┴──────────────────┴──────────────────────────────┘
```

---

### `engram status`

Show local store status and optionally live metagraph data.

```bash
# Local status only
engram status
```

```
╭─ Engram Status ──────────────────────────────────────────╮
│ Vectors stored:   42156                                   │
│ Embedder:         local (384d)                            │
│ engram-core:      ✓ built                                 │
│ Index path:       ./data/engram.index                     │
│ Network:          ws://127.0.0.1:9944                     │
│ Wallet:           default                                 │
╰───────────────────────────────────────────────────────────╯
```

```bash
# Live metagraph (connects to chain, health-probes all miners)
engram status --live
engram status --live --netuid 42
```

**Flags:**

| Flag | Description |
|------|-------------|
| `--live, -l` | Fetch live data from the chain and probe all miners |
| `--netuid INT` | Subnet UID (overrides `NETUID` env var) |

**Live output:**

```
Fetching metagraph | network=ws://127.0.0.1:9944 | netuid=2

┌─────────────────────────────────────────────────────────────────────────────┐
│                          Subnet 2 Neurons                                   │
├─────┬──────────────────────┬─────────────────┬────────────┬──────┬──────────┤
│ UID │ Hotkey               │ IP:Port         │ Stake      │Trust │ Health   │
├─────┼──────────────────────┼─────────────────┼────────────┼──────┼──────────┤
│   0 │ 5FHGPfix… ← you      │ 127.0.0.1:8091  │ 0.0001τ   │ 0.00 │ ✓ 1024v │
│   1 │ 5DkQn4n3…            │ 127.0.0.1:8093  │ 0.0001τ   │ 0.00 │ ✓ 512v  │
└─────┴──────────────────────┴─────────────────┴────────────┴──────┴──────────┘

Block: 42810 | 2 neurons registered
```

---

### `engram demo`

Run the local end-to-end demo: seed corpus → ingest → query → score.

```bash
engram demo
```

Equivalent to running `python scripts/run_demo.py`.

---

## Environment Variables

The CLI reads these from `.env` (auto-loaded on startup):

| Variable | Default | Description |
|----------|---------|-------------|
| `FAISS_INDEX_PATH` | `./data/engram.index` | Local FAISS index file |
| `USE_LOCAL_EMBEDDER` | `true` (CLI default) | Use sentence-transformers instead of OpenAI |
| `OPENAI_API_KEY` | — | Required if `USE_LOCAL_EMBEDDER=false` |
| `SUBTENSOR_NETWORK` | — | Network for `--live` (e.g. `finney`, `ws://...`) |
| `SUBTENSOR_ENDPOINT` | — | WebSocket endpoint (overrides `SUBTENSOR_NETWORK`) |
| `NETUID` | `99` | Default subnet UID for `--live` |
| `WALLET_NAME` | `default` | Wallet name (for "← you" marker in `--live`) |
| `WALLET_HOTKEY` | `default` | Hotkey name |
| `MINER_PORT` | `8091` | Fallback port when axon.port is 0 |
| `MINER_IP` | `127.0.0.1` | Fallback IP when axon.ip is 0.0.0.0 |
