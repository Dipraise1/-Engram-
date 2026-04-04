"""
Engram — LlamaIndex VectorStore adapter

Implements the LlamaIndex BasePydanticVectorStore interface so Engram can
serve as a persistent retrieval backend in any LlamaIndex pipeline.

Install:
    pip install llama-index-core engram-subnet

Usage:
    from llama_index.core import VectorStoreIndex, Document
    from llama_index.core.storage.storage_context import StorageContext
    from engram.sdk.llama_index import EngramVectorStore

    # Build an index backed by Engram
    store = EngramVectorStore(miner_url="http://127.0.0.1:8091")
    storage_context = StorageContext.from_defaults(vector_store=store)

    documents = [Document(text="The transformer architecture...")]
    index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)

    # Query
    query_engine = index.as_query_engine()
    response = query_engine.query("how does attention work?")
    print(response)
"""

from __future__ import annotations

from typing import Any, Optional, Sequence, cast

from engram.sdk.client import EngramClient
from engram.sdk.exceptions import IngestError

try:
    from llama_index.core.schema import (
        BaseNode,
        NodeWithScore,
        TextNode,
    )
    from llama_index.core.vector_stores.types import (
        BasePydanticVectorStore,
        VectorStoreQuery,
        VectorStoreQueryResult,
    )

    _LLAMA_AVAILABLE = True
except ImportError:
    _LLAMA_AVAILABLE = False


def _require_llama() -> None:
    if not _LLAMA_AVAILABLE:
        raise ImportError(
            "llama-index-core is required for EngramVectorStore (LlamaIndex). "
            "Install it with: pip install llama-index-core"
        )


class EngramVectorStore:
    """
    LlamaIndex-compatible vector store backed by an Engram miner.

    Stores nodes as embeddings on the miner. Retrieval uses the miner's
    HNSW approximate nearest-neighbor index.

    Args:
        miner_url: Base URL of the miner's HTTP server.
        timeout:   HTTP timeout in seconds.
    """

    stores_text: bool = True
    is_embedding_query: bool = True
    flat_metadata: bool = False

    def __init__(
        self,
        miner_url: str = "http://127.0.0.1:8091",
        timeout: float = 30.0,
    ) -> None:
        _require_llama()
        self._client = EngramClient(miner_url=miner_url, timeout=timeout)

    # ── BasePydanticVectorStore interface ──────────────────────────────────────

    def add(
        self,
        nodes: Sequence[Any],
        **add_kwargs: Any,
    ) -> list[str]:
        """
        Store nodes on the Engram miner.

        Each node's embedding is stored as a raw vector; its text and
        metadata are stored alongside for retrieval.

        Returns:
            List of CIDs assigned to each stored node.
        """
        _require_llama()
        cids = []

        for node in nodes:
            meta: dict[str, Any] = {
                "node_id": node.node_id,
                "text": node.get_content(),
            }
            meta.update(node.metadata or {})

            if node.embedding is not None:
                cid = self._client.ingest_embedding(
                    node.embedding,
                    metadata=meta,
                )
            else:
                cid = self._client.ingest(
                    node.get_content(),
                    metadata=meta,
                )
            cids.append(cid)

        return cids

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        """
        Engram is append-only by design — deletions are not supported.
        This is a no-op so LlamaIndex pipelines don't error.
        """
        pass

    def query(self, query: Any, **kwargs: Any) -> Any:
        """
        Execute a vector query against the miner.

        Args:
            query: VectorStoreQuery with query_embedding and similarity_top_k.

        Returns:
            VectorStoreQueryResult with nodes and similarities.
        """
        _require_llama()

        if query.query_embedding is not None:
            results = self._client.query_by_vector(
                query.query_embedding,
                top_k=query.similarity_top_k or 4,
            )
        elif query.query_str:
            results = self._client.query(
                query.query_str,
                top_k=query.similarity_top_k or 4,
            )
        else:
            return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])

        nodes: list[Any] = []
        similarities: list[float] = []
        ids: list[str] = []

        for r in results:
            meta = dict(r.get("metadata") or {})
            text = meta.pop("text", "")
            node_id = meta.pop("node_id", r["cid"])
            meta["cid"] = r["cid"]

            node = TextNode(
                text=text,
                id_=node_id,
                metadata=meta,
            )
            nodes.append(NodeWithScore(node=node, score=float(r["score"])))
            similarities.append(float(r["score"]))
            ids.append(node_id)

        return VectorStoreQueryResult(nodes=nodes, similarities=similarities, ids=ids)

    # ── Convenience ────────────────────────────────────────────────────────────

    @classmethod
    def from_documents(
        cls,
        documents: list[Any],
        miner_url: str = "http://127.0.0.1:8091",
        **kwargs: Any,
    ) -> "EngramVectorStore":
        """
        Create an EngramVectorStore and index documents in one call.

        Example:
            from llama_index.core import Document
            store = EngramVectorStore.from_documents(
                [Document(text="my knowledge...")],
                miner_url="http://127.0.0.1:8091",
            )
        """
        _require_llama()
        from llama_index.core.schema import TextNode

        instance = cls(miner_url=miner_url, **kwargs)
        nodes = [
            TextNode(text=doc.text, metadata=doc.metadata or {})
            for doc in documents
        ]
        instance.add(nodes)
        return instance

    def health(self) -> bool:
        """Return True if the backing miner is reachable."""
        return self._client.is_online()

    def __repr__(self) -> str:
        return f"EngramVectorStore[LlamaIndex](miner_url={self._client.miner_url!r})"
