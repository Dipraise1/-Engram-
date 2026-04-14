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
vec = np.random.randn(384).astype(np.float32).tolist()
cid = client.ingest_embedding(vec, metadata={"type": "custom"})
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `embedding` | `list[float]` | Float32 vector (must match miner's `EMBEDDING_DIM`, default 384) |
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

---

## LangChain Integration

`EngramVectorStore` implements the LangChain `VectorStore` interface.

```bash
pip install langchain-core engram-subnet
```

```python
from langchain_openai import OpenAIEmbeddings
from engram.sdk.langchain import EngramVectorStore

embeddings = OpenAIEmbeddings()
store = EngramVectorStore(miner_url="http://127.0.0.1:8091", embeddings=embeddings)

# Store documents
store.add_texts(
    ["BERT uses bidirectional transformers.", "GPT generates text autoregressively."],
    metadatas=[{"source": "paper"}, {"source": "paper"}],
)

# Similarity search
docs = store.similarity_search("how does attention work?", k=5)
for doc in docs:
    print(doc.page_content, doc.metadata)

# With scores
docs_and_scores = store.similarity_search_with_score("transformers", k=3)
for doc, score in docs_and_scores:
    print(f"{score:.4f} — {doc.page_content}")

# Create from existing texts (one-liner)
store = EngramVectorStore.from_texts(texts, embedding=embeddings)

# Use as a LangChain retriever in any chain
retriever = store.as_retriever(search_kwargs={"k": 5})

from langchain.chains import RetrievalQA
chain = RetrievalQA.from_chain_type(llm=your_llm, retriever=retriever)
answer = chain.run("What is Bittensor?")
```

If `embeddings` is omitted, the miner's built-in embedder is used (canonical model). Pass `embeddings` to use your own model (e.g. OpenAI, Cohere, HuggingFace).

---

## LlamaIndex Integration

`EngramVectorStore` (from `engram.sdk.llama_index`) implements the LlamaIndex `BasePydanticVectorStore` interface.

```bash
pip install llama-index-core engram-subnet
```

```python
from llama_index.core import VectorStoreIndex, Document
from llama_index.core.storage.storage_context import StorageContext
from engram.sdk.llama_index import EngramVectorStore

# Build an index backed by Engram
store = EngramVectorStore(miner_url="http://127.0.0.1:8091")
storage_context = StorageContext.from_defaults(vector_store=store)

documents = [
    Document(text="Bittensor is a decentralised ML network."),
    Document(text="TAO tokens reward miners and validators."),
]
index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)

# Query
query_engine = index.as_query_engine()
response = query_engine.query("how does Bittensor distribute rewards?")
print(response)
```

---

## Agent Memory Pattern

Use Engram as persistent memory for AI agents — facts and context survive across sessions:

```python
from engram.sdk import EngramClient

client = EngramClient("http://127.0.0.1:8091")

# Agent stores what it learns
client.ingest("The user prefers concise responses.", metadata={"type": "preference"})
client.ingest("The user is building a Bittensor subnet.", metadata={"type": "context"})

# Before answering, agent retrieves relevant memory
context = client.query("what is the user building?", top_k=3)
for mem in context:
    print(mem["metadata"]["type"], "→", mem["score"])
```

Run the full demo: `python scripts/demo_agent_memory.py`
