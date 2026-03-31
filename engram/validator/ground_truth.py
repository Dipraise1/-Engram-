"""
Engram Validator — Ground Truth Manager

Maintains a set of known (text, embedding, CID) triples used to:
  1. Score miner recall@K
  2. Issue storage proof challenges

Ground truth is loaded from a JSONL file at startup and can be extended at runtime.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np
from loguru import logger


@dataclass
class GroundTruthEntry:
    text: str
    embedding: np.ndarray
    cid: str
    top_k_cids: list[str]   # known nearest-neighbor CIDs for recall scoring


class GroundTruthManager:
    def __init__(self, path: str | None = None) -> None:
        self._entries: list[GroundTruthEntry] = []
        if path and os.path.exists(path):
            self.load(path)

    def load(self, path: str) -> None:
        """Load ground truth entries from a JSONL file."""
        loaded = 0
        with open(path) as f:
            for line in f:
                obj = json.loads(line.strip())
                self._entries.append(GroundTruthEntry(
                    text=obj["text"],
                    embedding=np.array(obj["embedding"], dtype=np.float32),
                    cid=obj["cid"],
                    top_k_cids=obj.get("top_k_cids", [obj["cid"]]),
                ))
                loaded += 1
        logger.info(f"GroundTruth: loaded {loaded} entries from {path}")

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            for entry in self._entries:
                f.write(json.dumps({
                    "text": entry.text,
                    "embedding": entry.embedding.tolist(),
                    "cid": entry.cid,
                    "top_k_cids": entry.top_k_cids,
                }) + "\n")

    def add(self, entry: GroundTruthEntry) -> None:
        self._entries.append(entry)

    def sample(self, n: int = 10) -> list[GroundTruthEntry]:
        """Return a random sample of ground truth entries for evaluation."""
        import random
        k = min(n, len(self._entries))
        return random.sample(self._entries, k) if k else []

    def all_cids(self) -> list[str]:
        return [e.cid for e in self._entries]

    def __len__(self) -> int:
        return len(self._entries)
