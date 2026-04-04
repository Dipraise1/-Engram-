# Python SDK

`EngramClient` is a lightweight Python client for a single Engram miner node. No extra dependencies — uses only stdlib `urllib`.

---

## Installation

```bash
pip install engram-subnet
```

Or from source:

```bash
pip install -e .
```

---

## Quick Start

```python
from engram.sdk import EngramClient

client = EngramClient("http://127.0.0.1:8091")

# Store text
cid = client.ingest("The transformer architecture changed everything.")
print(cid)  # v1::a3f2b1...

# Semantic search
results = client.query("attention mechanisms in deep learning", top_k=5)
for r in results:
    print(f"{r['score']:.4f}  {r['cid']}")
```

---

## `EngramClient`

```python
EngramClient(miner_url: str = "http://127.0.0.1:8091", timeout: float = 30.0)
```

| Parameter | Description |
|-----------|-------------|
| `miner_url` | Base URL of the miner's HTTP server |
| `timeout` | Request timeout in seconds |

---

## Methods

### `ingest(text, metadata=None) → str`

Embed and store text on the miner.

```python
cid = client.ingest(
    "BERT uses bidirectional encoder representations.",
    metadata={"source": "arxiv", "year": "2018"}
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | `str` | Text to embed and store (max 8192 chars) |
| `metadata` | `dict` | Optional key-value metadata (max 4 KB JSON) |

**Returns:** CID string (`v1::...`)

**Raises:**
- `MinerOfflineError` — miner is unreachable
- `IngestError` — miner rejected the request (rate limit, stake check, etc.)
- `InvalidCIDError` — miner returned a malformed CID

---

### `ingest_embedding(embedding, metadata=None) → str`

Store a pre-computed embedding vector, skipping the embed step on the miner.

```python
import numpy as np
vec = np.random.randn(1536).astype(np.float32).tolist()
cid = client.ingest_embedding(vec, metadata={"type": "custom"})
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `embedding` | `list[float]` | Float32 vector (must match miner's `EMBEDDING_DIM`, default 1536) |
| `metadata` | `dict` | Optional metadata |

**Returns:** CID string

**Raises:** `MinerOfflineError`, `IngestError`, `InvalidCIDError`

---

### `query(text, top_k=10) → list[dict]`

Semantic search over the miner's stored embeddings.

```python
results = client.query("how does self-attention work?", top_k=10)
# [
#   {"cid": "v1::a3f2b1...", "score": 0.9821, "metadata": {"source": "arxiv"}},
#   ...
# ]
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | `str` | Query text |
| `top_k` | `int` | Max results to return (1–100) |

**Returns:** List of result dicts with keys `cid`, `score` (float, 0–1), `metadata`

**Raises:** `MinerOfflineError`, `QueryError`

---

### `query_by_vector(vector, top_k=10) → list[dict]`

ANN search using a pre-computed query vector.

```python
results = client.query_by_vector(my_embedding, top_k=5)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `vector` | `list[float]` | Float query vector |
| `top_k` | `int` | Max results |

**Returns:** List of `{cid, score, metadata}` dicts

---

### `batch_ingest_file(path, return_errors=False)`

Ingest all records from a JSONL file. Each line must be a JSON object with a `"text"` key and optional `"metadata"`.

```python
# data.jsonl:
# {"text": "Artificial intelligence is transforming industry"}
# {"text": "Deep learning requires large training datasets", "metadata": {"category": "ml"}}

cids = client.batch_ingest_file("data/corpus.jsonl")
print(f"Ingested {len(cids)} records")

# With error tracking
cids, errors = client.batch_ingest_file("data/corpus.jsonl", return_errors=True)
for err in errors:
    print(f"Skipped: {err}")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str \| Path` | Path to `.jsonl` file |
| `return_errors` | `bool` | If True, return `(cids, errors)` tuple |

**Returns:**
- `list[str]` — list of CIDs (default)
- `tuple[list[str], list[str]]` — `(cids, error_messages)` if `return_errors=True`

Lines that are malformed or missing `"text"` are skipped and captured in errors. If the miner goes offline mid-batch, `MinerOfflineError` is raised immediately.

---

### `health() → dict`

Check miner liveness.

```python
info = client.health()
# {"status": "ok", "vectors": 42156, "uid": 7, "peers": 12}
```

**Raises:** `MinerOfflineError`

---

### `is_online() → bool`

Returns `True` if the miner responds to a health check. Never raises.

```python
if client.is_online():
    cid = client.ingest("...")
```

---

## Exceptions

All exceptions inherit from `EngramError`:

```python
from engram.sdk import (
    EngramError,
    MinerOfflineError,
    IngestError,
    QueryError,
    InvalidCIDError,
)
```

| Exception | When raised |
|-----------|-------------|
| `EngramError` | Base class for all SDK errors |
| `MinerOfflineError` | Miner is unreachable (connection refused, timeout) |
| `IngestError` | Miner accepted the request but returned an error |
| `QueryError` | Miner accepted the query but returned an error |
| `InvalidCIDError` | Returned CID failed format validation |

```python
from engram.sdk import EngramClient, MinerOfflineError, IngestError

client = EngramClient("http://miner-host:8091")

try:
    cid = client.ingest("Some important text")
except MinerOfflineError as e:
    print(f"Miner is down: {e}")
except IngestError as e:
    print(f"Ingest rejected: {e}")  # rate limit, low stake, etc.
```

---

## Multi-Miner Pattern

To achieve redundancy, ingest to multiple miners:

```python
from engram.sdk import EngramClient, MinerOfflineError

miners = [
    EngramClient("http://miner1:8091"),
    EngramClient("http://miner2:8091"),
    EngramClient("http://miner3:8091"),
]

text = "Critical knowledge that must be preserved."
cids = []

for miner in miners:
    try:
        cids.append(miner.ingest(text))
    except MinerOfflineError:
        print(f"Miner offline: {miner.miner_url}")

print(f"Stored on {len(cids)}/3 miners")
```

Note: the same text always produces the same CID regardless of which miner stores it, because the CID is deterministically derived from the embedding content.

---

## JSONL Corpus Format

For `batch_ingest_file`, each line must be valid JSON with at minimum a `"text"` field:

```jsonl
{"text": "The first piece of knowledge"}
{"text": "Another entry", "metadata": {"source": "wikipedia", "lang": "en"}}
{"text": "Entry with nested metadata", "metadata": {"author": "Alice", "year": 2024}}
```

Lines missing `"text"` or with invalid JSON are silently skipped (captured in errors if `return_errors=True`).
