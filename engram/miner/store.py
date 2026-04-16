"""
Engram Miner — Vector Store

Abstraction over Qdrant (primary) and FAISS (fallback).
Qdrant runs as a separate Rust process — we talk to it via its Python client.
"""

from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
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


_PUBLIC_NS = "__public__"   # sentinel stored in payload to mark public records


@dataclass
class VectorRecord:
    cid: str
    embedding: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)
    namespace: str = _PUBLIC_NS


@dataclass
class SearchResult:
    cid: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Abstract base ─────────────────────────────────────────────────────────────

class VectorStore(ABC):
    @abstractmethod
    def upsert(self, record: VectorRecord) -> None: ...
    @abstractmethod
    def search(self, query: np.ndarray, top_k: int = DEFAULT_TOP_K, namespace: str = _PUBLIC_NS) -> list[SearchResult]: ...
    @abstractmethod
    def get(self, cid: str, namespace: str = _PUBLIC_NS) -> VectorRecord | None: ...
    @abstractmethod
    def delete(self, cid: str) -> bool: ...
    @abstractmethod
    def count(self) -> int: ...
    @abstractmethod
    def list(
        self,
        filter: dict[str, str] | None = None,
        limit: int = 50,
        offset: int = 0,
        namespace: str = _PUBLIC_NS,
    ) -> list[dict]: ...


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
            raise RuntimeError(
                "qdrant-client isn't installed. Install it with: pip install qdrant-client\n"
                "Also make sure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant"
            )

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
                    payload={
                        "cid": record.cid,
                        "_ns": record.namespace,
                        **record.metadata,
                    },
                )
            ],
        )

    def search(self, query: np.ndarray, top_k: int = DEFAULT_TOP_K, namespace: str = _PUBLIC_NS) -> list[SearchResult]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue, SearchParams
        ns_filter = Filter(
            must=[FieldCondition(key="_ns", match=MatchValue(value=namespace))]
        )
        results = self._client.query_points(
            collection_name=self._collection,
            query=query.tolist(),
            query_filter=ns_filter,
            limit=top_k,
            with_payload=True,
            search_params=SearchParams(hnsw_ef=HNSW_EF_SEARCH),
        )
        return [
            SearchResult(
                cid=(hit.payload or {}).get("cid", ""),
                score=float(hit.score),
                metadata={k: v for k, v in (hit.payload or {}).items() if k not in ("cid", "_ns")},
            )
            for hit in results.points
        ]

    def get(self, cid: str, namespace: str = _PUBLIC_NS) -> VectorRecord | None:
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
        stored_ns = (r.payload or {}).get("_ns", _PUBLIC_NS)
        # Enforce namespace isolation — don't return records from other namespaces
        if stored_ns != namespace:
            return None
        return VectorRecord(
            cid=cid,
            embedding=np.array(r.vector, dtype=np.float32),
            metadata={k: v for k, v in (r.payload or {}).items() if k not in ("cid", "_ns")},
            namespace=stored_ns,
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

    def list(
        self,
        filter: dict[str, str] | None = None,
        limit: int = 50,
        offset: int = 0,
        namespace: str = _PUBLIC_NS,
    ) -> list[dict]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant_filter = None
        conditions = []
        if namespace != _PUBLIC_NS:
            conditions.append(FieldCondition(key="namespace", match=MatchValue(value=namespace)))
        if filter:
            for k, v in filter.items():
                conditions.append(FieldCondition(key=k, match=MatchValue(value=str(v))))
        if conditions:
            qdrant_filter = Filter(must=conditions)

        results, _ = self._client.scroll(
            collection_name=self._collection,
            scroll_filter=qdrant_filter,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        return [
            {"cid": r.payload.get("cid", ""), "metadata": r.payload.get("metadata", {})}
            for r in results
        ]


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
            raise RuntimeError(
                "faiss-cpu isn't installed. Install it with: pip install faiss-cpu"
            )

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
        self._namespaces: dict[str, str] = {}   # cid → namespace
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
            internal_id = self._cid_to_id[record.cid]
        else:
            internal_id = self._next_id
            self._next_id += 1
            self._index.add(vec)
            self._id_to_cid[internal_id] = record.cid
            self._cid_to_id[record.cid] = internal_id

        self._metadata[record.cid] = record.metadata
        self._vectors[record.cid] = record.embedding
        self._namespaces[record.cid] = record.namespace

    def search(self, query: np.ndarray, top_k: int = DEFAULT_TOP_K, namespace: str = _PUBLIC_NS) -> list[SearchResult]:
        import faiss

        if self._index.ntotal == 0:
            return []

        vec = query.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(vec)

        # Over-fetch to account for namespace filtering reducing the result set
        fetch_k = min(top_k * 10, self._index.ntotal)
        distances, indices = self._index.search(vec, fetch_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            cid = self._id_to_cid.get(int(idx))
            if cid is None:
                continue
            # Enforce namespace isolation
            if self._namespaces.get(cid, _PUBLIC_NS) != namespace:
                continue
            results.append(SearchResult(
                cid=cid,
                score=float(dist),
                metadata=self._metadata.get(cid, {}),
            ))
            if len(results) >= top_k:
                break
        return results

    def get(self, cid: str, namespace: str = _PUBLIC_NS) -> VectorRecord | None:
        if cid not in self._vectors:
            return None
        # Enforce namespace isolation
        if self._namespaces.get(cid, _PUBLIC_NS) != namespace:
            return None
        return VectorRecord(
            cid=cid,
            embedding=self._vectors[cid],
            metadata=self._metadata.get(cid, {}),
            namespace=self._namespaces.get(cid, _PUBLIC_NS),
        )

    def delete(self, cid: str) -> bool:
        if cid not in self._cid_to_id:
            return False
        # FAISS HNSW doesn't support physical removal, so we tombstone the slot:
        # remove the internal-ID→CID mapping so search() skips it on the next hit.
        internal_id = self._cid_to_id.pop(cid)
        self._id_to_cid.pop(internal_id, None)
        self._metadata.pop(cid, None)
        self._vectors.pop(cid, None)
        self._namespaces.pop(cid, None)
        return True

    def count(self) -> int:
        # Return logical count (excludes tombstoned vectors) rather than
        # FAISS ntotal, which includes physically-present but deleted slots.
        return len(self._vectors)

    def list(
        self,
        filter: dict[str, str] | None = None,
        limit: int = 50,
        offset: int = 0,
        namespace: str = _PUBLIC_NS,
    ) -> list[dict]:
        """Return a paginated, optionally filtered list of stored records.

        filter is matched against metadata fields — all key/value pairs must match
        (AND semantics). Values are compared as strings.
        """
        results = []
        for cid, meta in self._metadata.items():
            if self._namespaces.get(cid, _PUBLIC_NS) != namespace:
                continue
            if filter:
                if not all(str(meta.get(k)) == str(v) for k, v in filter.items()):
                    continue
            results.append({"cid": cid, "metadata": meta})

        # Stable sort by insertion order approximated via cid_to_id
        results.sort(key=lambda r: self._cid_to_id.get(r["cid"], 0))
        return results[offset: offset + limit]

    def save(self, path: str | None = None) -> None:
        import faiss
        import json
        target = path or self._index_path
        if target:
            faiss.write_index(self._index, target)
            # Persist ID maps, metadata, and vectors as JSON (no pickle — avoids RCE on load)
            meta_path = target + ".meta.json"
            payload = {
                "id_to_cid": {str(k): v for k, v in self._id_to_cid.items()},
                "cid_to_id": self._cid_to_id,
                "metadata": self._metadata,
                "vectors": {cid: emb.tolist() for cid, emb in self._vectors.items()},
                "namespaces": self._namespaces,
                "next_id": self._next_id,
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)

    def load(self, path: str) -> None:
        import faiss
        import json
        self._index = faiss.read_index(path)
        # Prefer the new JSON meta file; fall back to legacy pickle only if it exists
        json_meta_path = path + ".meta.json"
        legacy_meta_path = path + ".meta"
        if os.path.exists(json_meta_path):
            with open(json_meta_path, encoding="utf-8") as f:
                data = json.load(f)
            self._id_to_cid  = {int(k): v for k, v in data.get("id_to_cid", {}).items()}
            self._cid_to_id  = data.get("cid_to_id", {})
            self._metadata   = data.get("metadata", {})
            self._vectors    = {
                cid: np.array(v, dtype=np.float32)
                for cid, v in data.get("vectors", {}).items()
            }
            self._namespaces = data.get("namespaces", {})
            self._next_id    = data.get("next_id", self._index.ntotal)
        elif os.path.exists(legacy_meta_path):
            # One-time migration: load old pickle file, immediately re-save as JSON
            import pickle  # noqa: S403 — intentional legacy migration only
            logger.warning(
                f"Migrating legacy pickle meta at {legacy_meta_path} → JSON. "
                "Delete the .meta file after confirming the migration succeeded."
            )
            with open(legacy_meta_path, "rb") as f:
                data = pickle.load(f)  # noqa: S301
            self._id_to_cid = data.get("id_to_cid", {})
            self._cid_to_id = data.get("cid_to_id", {})
            self._metadata  = data.get("metadata", {})
            self._vectors   = data.get("vectors", {})
            self._next_id   = data.get("next_id", self._index.ntotal)
            self.save(path)  # immediately write the JSON version


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
    raise ValueError(
        f"'{backend}' isn't a recognised vector store. "
        "Set VECTOR_STORE_BACKEND to 'qdrant' or 'faiss' in your .env file."
    )
