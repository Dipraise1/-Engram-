from engram.sdk.client import EngramClient
from engram.sdk.exceptions import (
    EngramError,
    MinerOfflineError,
    IngestError,
    QueryError,
    InvalidCIDError,
)

__all__ = [
    "EngramClient",
    "EngramError",
    "MinerOfflineError",
    "IngestError",
    "QueryError",
    "InvalidCIDError",
    # Framework adapters (imported lazily to avoid hard deps)
    "EngramVectorStore",
]


def __getattr__(name: str):
    if name == "EngramVectorStore":
        # Try LangChain first, then LlamaIndex
        try:
            from engram.sdk.langchain import EngramVectorStore
            return EngramVectorStore
        except ImportError:
            pass
        try:
            from engram.sdk.llama_index import EngramVectorStore as _LIVectorStore
            return _LIVectorStore
        except ImportError:
            pass
        raise ImportError(
            "EngramVectorStore requires langchain-core or llama-index-core. "
            "Install with: pip install langchain-core  or  pip install llama-index-core"
        )
    raise AttributeError(f"module 'engram.sdk' has no attribute {name!r}")
