"""
Engram Miner — Embedder

Wraps embedding model calls. The canonical model is locked per subnet epoch.
Supports OpenAI API (default) and local sentence-transformers (fallback / offline).
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
from loguru import logger

from engram.config import CANONICAL_MODEL, EMBEDDING_DIM


class Embedder:
    """
    Produces float32 numpy embeddings from text.

    The active backend is selected at construction time:
      - "openai"  → OpenAI text-embedding-3-small (canonical)
      - "local"   → sentence-transformers/all-MiniLM-L6-v2 (offline / testing)
    """

    def __init__(self, backend: str = "openai") -> None:
        self.backend = backend
        self._client = None
        self._local_model = None

        if backend == "openai":
            self._init_openai()
        elif backend == "local":
            self._init_local()
        else:
            raise ValueError(f"Unknown embedder backend: {backend!r}")

    # ── Init ──────────────────────────────────────────────────────────────────

    def _init_openai(self) -> None:
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
            logger.info(f"Embedder: OpenAI backend ({CANONICAL_MODEL})")
        except ImportError:
            raise RuntimeError(
                "The OpenAI package isn't installed. Fix it with: pip install openai"
            )
        except KeyError:
            raise RuntimeError(
                "Missing OPENAI_API_KEY. Add it to your .env file:\n"
                "  OPENAI_API_KEY=sk-...\n"
                "Or switch to the local embedder: USE_LOCAL_EMBEDDER=true"
            )

    def _init_local(self) -> None:
        try:
            import torch
            from sentence_transformers import SentenceTransformer
            model_name = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
                
            self._local_model = SentenceTransformer(model_name, device=device)
            logger.info(f"Embedder: local sentence-transformers ({model_name}) on {device}")
        except ImportError:
            raise RuntimeError(
                "Local embedding requires sentence-transformers and torch. Install them with:\n"
                "  pip install sentence-transformers torch"
            )

    # ── Public API ────────────────────────────────────────────────────────────

    @lru_cache(maxsize=10000)
    def embed(self, text: str) -> np.ndarray:
        """Embed a single text string. Returns a float32 numpy array."""
        text = text.strip()
        if not text:
            raise ValueError("Got empty text — there's nothing to embed here.")

        if self.backend == "openai":
            # Return copy to prevent accidental mutation of cached arrays
            return self._embed_openai(text).copy()
        return self._embed_local(text).copy()

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed multiple texts. Returns a list of float32 arrays."""
        if not texts:
            return []
        if self.backend == "openai":
            return self._embed_openai_batch(texts)
        return self._embed_local_batch(texts)

    @property
    def dim(self) -> int:
        if self.backend == "local" and self._local_model is not None:
            return self._local_model.get_sentence_embedding_dimension() or EMBEDDING_DIM
        return EMBEDDING_DIM

    # ── Backends ──────────────────────────────────────────────────────────────

    def _embed_openai(self, text: str) -> np.ndarray:
        response = self._client.embeddings.create(
            input=text,
            model=CANONICAL_MODEL,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    def _embed_openai_batch(self, texts: list[str]) -> list[np.ndarray]:
        response = self._client.embeddings.create(
            input=texts,
            model=CANONICAL_MODEL,
        )
        return [np.array(item.embedding, dtype=np.float32) for item in response.data]

    def _embed_local(self, text: str) -> np.ndarray:
        vec = self._local_model.encode(text, normalize_embeddings=True)
        return np.array(vec, dtype=np.float32)

    def _embed_local_batch(self, texts: list[str]) -> list[np.ndarray]:
        vecs = self._local_model.encode(texts, normalize_embeddings=True)
        return [np.array(v, dtype=np.float32) for v in vecs]


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Singleton embedder — constructed once per process."""
    backend = "local" if os.getenv("USE_LOCAL_EMBEDDER", "false").lower() == "true" else "openai"
    return Embedder(backend=backend)
