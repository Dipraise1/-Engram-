"""
Engram — LangChain VectorStore adapter

Implements langchain_core.vectorstores.VectorStore so Engram can be used
as a drop-in memory/retrieval backend in any LangChain application.

Install:
    pip install langchain-core engram-subnet

Usage:
    from langchain_openai import OpenAIEmbeddings
    from engram.sdk.langchain import EngramVectorStore

    embeddings = OpenAIEmbeddings()
    store = EngramVectorStore(miner_url="http://127.0.0.1:8091", embeddings=embeddings)

    # Add documents
    store.add_texts(["The transformer architecture...", "BERT uses bidirectional..."])

    # Similarity search
    docs = store.similarity_search("how does attention work?", k=5)
    for doc in docs:
        print(doc.page_content, doc.metadata)

    # With scores
    docs_and_scores = store.similarity_search_with_score("transformers", k=3)
    for doc, score in docs_and_scores:
        print(f"{score:.4f} — {doc.page_content[:80]}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from engram.sdk.client import EngramClient
from engram.sdk.exceptions import IngestError, MinerOfflineError

if TYPE_CHECKING:
    pass

try:
    from langchain_core.documents import Document
    from langchain_core.embeddings import Embeddings
    from langchain_core.vectorstores import VectorStore

    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False


def _require_langchain() -> None:
    if not _LANGCHAIN_AVAILABLE:
        raise ImportError(
            "langchain-core is required for EngramVectorStore. "
            "Install it with: pip install langchain-core"
        )


class EngramVectorStore:
    """
    LangChain-compatible VectorStore backed by an Engram miner.

    Stores documents as embeddings on the miner. Retrieval uses
    the miner's HNSW approximate nearest-neighbor index.

    Args:
        miner_url:   Base URL of the miner's HTTP server.
        embeddings:  A LangChain Embeddings object (e.g. OpenAIEmbeddings).
        timeout:     HTTP timeout in seconds.
    """

    def __init__(
        self,
        miner_url: str = "http://127.0.0.1:8091",
        embeddings: Any = None,
        timeout: float = 30.0,
    ) -> None:
        _require_langchain()
        self._client = EngramClient(miner_url=miner_url, timeout=timeout)
        self._embeddings = embeddings

    # ── Core VectorStore interface ─────────────────────────────────────────────

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: list[dict] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """
        Embed and store texts on the Engram miner.

        Returns:
            List of CIDs assigned to each stored document.
        """
        texts = list(texts)
        cids = []

        if self._embeddings is not None:
            # Batch embed, then store pre-computed vectors
            vectors = self._embeddings.embed_documents(texts)
            for i, (text, vec) in enumerate(zip(texts, vectors)):
                meta = (metadatas[i] if metadatas and i < len(metadatas) else {})
                meta.setdefault("text", text)
                try:
                    cid = self._client.ingest_embedding(vec, metadata=meta)
                    cids.append(cid)
                except IngestError as exc:
                    raise IngestError(f"Failed to store text at index {i}: {exc}") from exc
        else:
            # Let the miner embed (uses its canonical model)
            for i, text in enumerate(texts):
                meta = (metadatas[i] if metadatas and i < len(metadatas) else {})
                try:
                    cid = self._client.ingest(text, metadata=meta)
                    cids.append(cid)
                except IngestError as exc:
                    raise IngestError(f"Failed to store text at index {i}: {exc}") from exc

        return cids

    def add_documents(
        self,
        documents: list[Any],
        **kwargs: Any,
    ) -> list[str]:
        """Store LangChain Document objects."""
        _require_langchain()
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        return self.add_texts(texts, metadatas=metadatas, **kwargs)

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        **kwargs: Any,
    ) -> list[Any]:
        """
        Return the top-k most similar documents for a text query.

        Returns:
            List of LangChain Document objects.
        """
        _require_langchain()
        docs_and_scores = self.similarity_search_with_score(query, k=k)
        return [doc for doc, _ in docs_and_scores]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        **kwargs: Any,
    ) -> list[tuple[Any, float]]:
        """
        Return top-k documents with their cosine similarity scores.

        Returns:
            List of (Document, score) tuples, score in [0, 1].
        """
        _require_langchain()

        if self._embeddings is not None:
            vec = self._embeddings.embed_query(query)
            results = self._client.query_by_vector(vec, top_k=k)
        else:
            results = self._client.query(query, top_k=k)

        docs = []
        for r in results:
            meta = dict(r.get("metadata") or {})
            # Recover page_content from metadata["text"] if present, else use CID
            content = meta.pop("text", r.get("cid", ""))
            meta["cid"] = r["cid"]
            doc = Document(page_content=content, metadata=meta)
            docs.append((doc, float(r["score"])))

        return docs

    def similarity_search_by_vector(
        self,
        embedding: list[float],
        k: int = 4,
        **kwargs: Any,
    ) -> list[Any]:
        """Return top-k documents using a pre-computed embedding vector."""
        _require_langchain()
        results = self._client.query_by_vector(embedding, top_k=k)
        docs = []
        for r in results:
            meta = dict(r.get("metadata") or {})
            content = meta.pop("text", r.get("cid", ""))
            meta["cid"] = r["cid"]
            docs.append(Document(page_content=content, metadata=meta))
        return docs

    # ── Convenience ────────────────────────────────────────────────────────────

    @classmethod
    def from_texts(
        cls,
        texts: list[str],
        embedding: Any,
        metadatas: list[dict] | None = None,
        miner_url: str = "http://127.0.0.1:8091",
        **kwargs: Any,
    ) -> "EngramVectorStore":
        """
        Create an EngramVectorStore and populate it with texts in one call.

        Example:
            store = EngramVectorStore.from_texts(
                texts=["doc1", "doc2"],
                embedding=OpenAIEmbeddings(),
                miner_url="http://127.0.0.1:8091",
            )
        """
        instance = cls(miner_url=miner_url, embeddings=embedding, **kwargs)
        instance.add_texts(texts, metadatas=metadatas)
        return instance

    def as_retriever(self, search_kwargs: dict | None = None) -> Any:
        """
        Return a LangChain VectorStoreRetriever wrapping this store.

        Example:
            retriever = store.as_retriever(search_kwargs={"k": 5})
            chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
        """
        _require_langchain()
        from langchain_core.vectorstores import VectorStoreRetriever
        return VectorStoreRetriever(
            vectorstore=self,  # type: ignore[arg-type]
            search_kwargs=search_kwargs or {"k": 4},
        )

    def health(self) -> bool:
        """Return True if the backing miner is reachable."""
        return self._client.is_online()

    def __repr__(self) -> str:
        return f"EngramVectorStore(miner_url={self._client.miner_url!r})"
