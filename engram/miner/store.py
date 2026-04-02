"""
Engram Miner — Vector Store

Abstraction over Qdrant (primary) and FAISS (fallback).
Qdrant runs as a separate Rust process — we talk to it via its Python client.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from loguru import logger

from engram.config import (
    DEFAULT_TOP_K,
    EMBEDDING_DIM,
    HNSW_EF_CONSTRUCTION,
    HNSW_EF_SEARCH,
    HNSW_M,
)


@dataclass
class VectorRecord:
    cid: str
    embedding: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    cid: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Abstract base ─────────────────────────────────────────────────────────────

class VectorStore:
    def upsert(self, record: VectorRecord) -> None: ...
    def search(self, query: np.ndarray, top_k: int = DEFAULT_TOP_K) -> list[SearchResult]: ...
    def get(self, cid: str) -> VectorRecord | None: ...
    def delete(self, cid: str) -> bool: ...
    def count(self) -> int: ...


# ── Qdrant backend ────────────────────────────────────────────────────────────

class QdrantStore(VectorStore):
    """
    Wraps the Qdrant Python client.
    Qdrant itself is a Rust binary — run it via Docker or the binary.

    docker run -p 6333:6333 qdrant/qdrant
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection: str = "engram",
        dim: int = EMBEDDING_DIM,
    ) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import (
                Distance,
                HnswConfigDiff,
                VectorParams,
            )
        except ImportError:
            raise RuntimeError("qdrant-client not installed. Run: pip install qdrant-client")

        self._client = QdrantClient(host=host, port=port)
        self._collection = collection
        self._dim = dim

        # Create collection if it doesn't exist
        existing = [c.name for c in self._client.get_collections().collections]
        if collection not in existing:
            self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(
                    size=dim,
                    distance=Distance.COSINE,
                    hnsw_config=HnswConfigDiff(
                        m=HNSW_M,
                        ef_construct=HNSW_EF_CONSTRUCTION,
                    ),
                ),
            )
            logger.info(f"QdrantStore: created collection '{collection}' (dim={dim})")
        else:
            logger.info(f"QdrantStore: connected to existing collection '{collection}'")

    def upsert(self, record: VectorRecord) -> None:
        from qdrant_client.models import PointStruct

        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, record.cid)),
                    vector=record.embedding.tolist(),
                    payload={"cid": record.cid, **record.metadata},
                )
            ],
        )

    def search(self, query: np.ndarray, top_k: int = DEFAULT_TOP_K) -> list[SearchResult]:
        hits = self._client.search(
            collection_name=self._collection,
            query_vector=query.tolist(),
            limit=top_k,
            with_payload=True,
            search_params={"hnsw_ef": HNSW_EF_SEARCH},
        )
        return [
            SearchResult(
                cid=hit.payload.get("cid", ""),
                score=float(hit.score),
                metadata={k: v for k, v in hit.payload.items() if k != "cid"},
            )
            for hit in hits
        ]

    def get(self, cid: str) -> VectorRecord | None:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, cid))
        results = self._client.retrieve(
            collection_name=self._collection,
            ids=[point_id],
            with_vectors=True,
            with_payload=True,
        )
        if not results:
            return None
        r = results[0]
        return VectorRecord(
            cid=cid,
            embedding=np.array(r.vector, dtype=np.float32),
            metadata={k: v for k, v in r.payload.items() if k != "cid"},
        )

    def delete(self, cid: str) -> bool:
        from qdrant_client.models import PointIdsList

        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, cid))
        self._client.delete(
            collection_name=self._collection,
            points_selector=PointIdsList(points=[point_id]),
        )
        return True

    def count(self) -> int:
        info = self._client.get_collection(self._collection)
        return info.points_count or 0


# ── FAISS backend ─────────────────────────────────────────────────────────────

class FAISSStore(VectorStore):
    """
    In-process FAISS HNSW index. Good for local testing; for production use Qdrant.
    Does NOT persist between restarts unless you call save()/load().
    """

    def __init__(self, dim: int = EMBEDDING_DIM, index_path: str | None = None) -> None:
        try:
            import faiss
        except ImportError:
            raise RuntimeError("faiss-cpu not installed. Run: pip install faiss-cpu")

        import faiss

        self._dim = dim
        self._index_path = index_path

        self._index = faiss.IndexHNSWFlat(dim, HNSW_M)
        self._index.hnsw.efConstruction = HNSW_EF_CONSTRUCTION
        self._index.hnsw.efSearch = HNSW_EF_SEARCH

        # CID ↔ internal ID mapping
        self._id_to_cid: dict[int, str] = {}
        self._cid_to_id: dict[str, int] = {}
        self._metadata: dict[str, dict[str, Any]] = {}
        self._vectors: dict[str, np.ndarray] = {}
        self._next_id: int = 0

        if index_path and os.path.exists(index_path):
            self.load(index_path)
            logger.info(f"FAISSStore: loaded index from {index_path}")
        else:
            logger.info(f"FAISSStore: new in-memory index (dim={dim})")

    def upsert(self, record: VectorRecord) -> None:
        import faiss

        vec = record.embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(vec)

        if record.cid in self._cid_to_id:
            # FAISS HNSW doesn't support in-place update; just overwrite metadata
            internal_id = self._cid_to_id[record.cid]
        else:
            internal_id = self._next_id
            self._next_id += 1
            self._index.add(vec)
            self._id_to_cid[internal_id] = record.cid
            self._cid_to_id[record.cid] = internal_id

        self._metadata[record.cid] = record.metadata
        self._vectors[record.cid] = record.embedding

    def search(self, query: np.ndarray, top_k: int = DEFAULT_TOP_K) -> list[SearchResult]:
        import faiss

        if self._index.ntotal == 0:
            return []

        vec = query.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(vec)

        k = min(top_k, self._index.ntotal)
        distances, indices = self._index.search(vec, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            cid = self._id_to_cid.get(int(idx))
            if cid is None:
                continue
            results.append(SearchResult(
                cid=cid,
                score=float(dist),
                metadata=self._metadata.get(cid, {}),
            ))
        return results

    def get(self, cid: str) -> VectorRecord | None:
        if cid not in self._vectors:
            return None
        return VectorRecord(
            cid=cid,
            embedding=self._vectors[cid],
            metadata=self._metadata.get(cid, {}),
        )

    def delete(self, cid: str) -> bool:
        if cid not in self._cid_to_id:
            return False
        # FAISS HNSW doesn't support removal; mark as deleted
        del self._cid_to_id[cid]
        self._metadata.pop(cid, None)
        self._vectors.pop(cid, None)
        return True

    def count(self) -> int:
        return self._index.ntotal

    def save(self, path: str | None = None) -> None:
        import faiss
        import pickle
        target = path or self._index_path
        if target:
            faiss.write_index(self._index, target)
            # Persist ID maps and metadata alongside the index
            meta_path = target + ".meta"
            with open(meta_path, "wb") as f:
                pickle.dump({
                    "id_to_cid": self._id_to_cid,
                    "cid_to_id": self._cid_to_id,
                    "metadata": self._metadata,
                    "vectors": self._vectors,
                    "next_id": self._next_id,
                }, f)

    def load(self, path: str) -> None:
        import faiss
        import pickle
        self._index = faiss.read_index(path)
        meta_path = path + ".meta"
        if os.path.exists(meta_path):
            with open(meta_path, "rb") as f:
                data = pickle.load(f)
            self._id_to_cid = data.get("id_to_cid", {})
            self._cid_to_id = data.get("cid_to_id", {})
            self._metadata  = data.get("metadata", {})
            self._vectors   = data.get("vectors", {})
            self._next_id   = data.get("next_id", self._index.ntotal)


# ── Factory ───────────────────────────────────────────────────────────────────

def build_store(backend: str = "qdrant") -> VectorStore:
    if backend == "qdrant":
        return QdrantStore(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            collection=os.getenv("QDRANT_COLLECTION", "engram"),
        )
    elif backend == "faiss":
        return FAISSStore(
            index_path=os.getenv("FAISS_INDEX_PATH"),
        )
    raise ValueError(f"Unknown vector store backend: {backend!r}")
