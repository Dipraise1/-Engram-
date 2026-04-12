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
import secrets
import tempfile
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
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(f"GroundTruth: skipping malformed JSON at line {lineno}: {exc}")
                    continue
                if not isinstance(obj.get("text"), str) or not isinstance(obj.get("cid"), str):
                    logger.warning(f"GroundTruth: skipping entry at line {lineno}: missing/invalid 'text' or 'cid'")
                    continue
                raw_emb = obj.get("embedding")
                if not isinstance(raw_emb, list) or not raw_emb:
                    logger.warning(f"GroundTruth: skipping entry at line {lineno}: missing/invalid 'embedding'")
                    continue
                self._entries.append(GroundTruthEntry(
                    text=obj["text"],
                    embedding=np.array(raw_emb, dtype=np.float32),
                    cid=obj["cid"],
                    top_k_cids=obj.get("top_k_cids", [obj["cid"]]),
                ))
                loaded += 1
        logger.info(f"GroundTruth: loaded {loaded} entries from {path}")

    def save(self, path: str) -> None:
        """Write entries atomically — crash during write won't corrupt the existing file."""
        dir_ = os.path.dirname(os.path.abspath(path))
        fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                for entry in self._entries:
                    f.write(json.dumps({
                        "text": entry.text,
                        "embedding": entry.embedding.tolist(),
                        "cid": entry.cid,
                        "top_k_cids": entry.top_k_cids,
                    }) + "\n")
            os.replace(tmp_path, path)
        except Exception:
            os.unlink(tmp_path)
            raise

    def add(self, entry: GroundTruthEntry) -> None:
        self._entries.append(entry)

    def sample(self, n: int = 10) -> list[GroundTruthEntry]:
        """Return a cryptographically random sample of ground truth entries for evaluation."""
        k = min(n, len(self._entries))
        if not k:
            return []
        indices = secrets.SystemRandom().sample(range(len(self._entries)), k)
        return [self._entries[i] for i in indices]

    def all_cids(self) -> list[str]:
        return [e.cid for e in self._entries]

    def __len__(self) -> int:
        return len(self._entries)
