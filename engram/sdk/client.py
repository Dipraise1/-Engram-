"""
Engram SDK — EngramClient

High-level Python client for the Engram decentralized vector database.

Usage:
    from engram.sdk import EngramClient

    client = EngramClient("http://127.0.0.1:8091")

    cid = client.ingest("The transformer architecture changed everything.")
    results = client.query("attention mechanisms in deep learning", top_k=5)
    for r in results:
        print(r["cid"], r["score"])
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from engram.cid import parse_cid
from engram.sdk.exceptions import (
    EngramError,
    IngestError,
    InvalidCIDError,
    MinerOfflineError,
    QueryError,
)


class EngramClient:
    """
    Client for a single Engram miner node.

    Args:
        miner_url: Base URL of the miner's HTTP server, e.g. "http://127.0.0.1:8091".
        timeout:   Request timeout in seconds (default 30).
    """

    def __init__(self, miner_url: str = "http://127.0.0.1:8091", timeout: float = 30.0) -> None:
        self.miner_url = miner_url.rstrip("/")
        self.timeout = timeout

    # ── Public API ─────────────────────────────────────────────────────────────

    def ingest(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Embed and store text on the miner.

        Args:
            text:     The text to embed and store.
            metadata: Optional key-value metadata stored alongside the vector.

        Returns:
            The CID (content identifier) assigned to this embedding.

        Raises:
            MinerOfflineError:  If the miner cannot be reached.
            IngestError:        If the miner returns an error.
            InvalidCIDError:    If the returned CID fails format validation.
        """
        payload = {"text": text, "metadata": metadata or {}}
        data = self._post("IngestSynapse", payload)

        if data.get("error"):
            raise IngestError(data["error"])

        cid = data.get("cid")
        if not cid:
            raise IngestError("Miner returned no CID and no error")

        self._validate_cid(cid)
        return cid

    def ingest_embedding(
        self,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Store a pre-computed embedding vector on the miner (skips embedding step).

        Args:
            embedding: Float vector (must match miner's EMBEDDING_DIM).
            metadata:  Optional metadata.

        Returns:
            CID assigned by the miner.

        Raises:
            MinerOfflineError, IngestError, InvalidCIDError
        """
        payload = {"raw_embedding": embedding, "metadata": metadata or {}}
        data = self._post("IngestSynapse", payload)

        if data.get("error"):
            raise IngestError(data["error"])

        cid = data.get("cid")
        if not cid:
            raise IngestError("Miner returned no CID and no error")

        self._validate_cid(cid)
        return cid

    def query(
        self,
        text: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Semantic search over the miner's stored embeddings.

        Args:
            text:  Query text to search for.
            top_k: Maximum number of results to return.

        Returns:
            List of result dicts, each with keys: "cid", "score", "metadata".
            Ordered by descending similarity score.

        Raises:
            MinerOfflineError, QueryError
        """
        payload = {"query_text": text, "top_k": top_k}
        data = self._post("QuerySynapse", payload)

        if data.get("error"):
            raise QueryError(data["error"])

        return data.get("results") or []

    def query_by_vector(
        self,
        vector: list[float],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        ANN search using a pre-computed query vector.

        Args:
            vector: Float query vector.
            top_k:  Maximum results.

        Returns:
            List of {cid, score, metadata} dicts.

        Raises:
            MinerOfflineError, QueryError
        """
        payload = {"query_vector": vector, "top_k": top_k}
        data = self._post("QuerySynapse", payload)

        if data.get("error"):
            raise QueryError(data["error"])

        return data.get("results") or []

    def batch_ingest_file(
        self,
        path: str | Path,
        return_errors: bool = False,
    ) -> list[str] | tuple[list[str], list[str]]:
        """
        Ingest all records from a JSONL file.

        Each line must be a JSON object with a "text" key (required) and an
        optional "metadata" dict. Lines that are malformed or missing "text"
        are skipped and captured as errors.

        Args:
            path:          Path to a .jsonl file.
            return_errors: If True, return (cids, errors) tuple instead of just cids.

        Returns:
            list[str]                     — list of CIDs (default)
            tuple[list[str], list[str]]   — (cids, error_messages) if return_errors=True

        Raises:
            FileNotFoundError if the file does not exist.
            MinerOfflineError if the miner is unreachable.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"JSONL file not found: {path}")

        cids: list[str] = []
        errors: list[str] = []

        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {lineno}: JSON parse error: {exc}")
                continue

            text = obj.get("text")
            if not text or not isinstance(text, str) or not text.strip():
                errors.append(f"line {lineno}: missing or empty 'text' field")
                continue

            metadata = obj.get("metadata") or {}

            try:
                cid = self.ingest(text, metadata=metadata)
                cids.append(cid)
            except IngestError as exc:
                errors.append(f"line {lineno}: ingest error: {exc}")
            # MinerOfflineError propagates — fail fast if miner goes down mid-batch

        if return_errors:
            return cids, errors
        return cids

    def health(self) -> dict[str, Any]:
        """
        Check miner liveness.

        Returns:
            Dict with keys: "status", "vectors", "uid".

        Raises:
            MinerOfflineError if the miner is unreachable.
        """
        return self._get("health")

    def is_online(self) -> bool:
        """Return True if the miner responds to a health check."""
        try:
            self.health()
            return True
        except MinerOfflineError:
            return False

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.miner_url}/{endpoint}"
        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except (ConnectionRefusedError, socket.timeout) as exc:
            raise MinerOfflineError(url, exc) from exc
        except urllib.error.URLError as exc:
            # urllib wraps connection errors in URLError
            reason = exc.reason
            if isinstance(reason, (ConnectionRefusedError, OSError)):
                raise MinerOfflineError(url, reason) from exc
            raise EngramError(f"HTTP request failed: {exc}") from exc
        except Exception as exc:
            raise EngramError(f"Unexpected error posting to {url}: {exc}") from exc

    def _get(self, endpoint: str) -> dict[str, Any]:
        url = f"{self.miner_url}/{endpoint}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except (ConnectionRefusedError, socket.timeout) as exc:
            raise MinerOfflineError(url, exc) from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (ConnectionRefusedError, OSError)):
                raise MinerOfflineError(url, reason) from exc
            raise EngramError(f"HTTP request failed: {exc}") from exc
        except Exception as exc:
            raise EngramError(f"Unexpected error fetching {url}: {exc}") from exc

    def _validate_cid(self, cid: str) -> None:
        """Raise InvalidCIDError if the CID format is wrong."""
        try:
            parse_cid(cid)
        except ValueError as exc:
            raise InvalidCIDError(cid) from exc

    def __repr__(self) -> str:
        return f"EngramClient(miner_url={self.miner_url!r}, timeout={self.timeout})"
