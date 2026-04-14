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
        miner_url:      Base URL of the miner's HTTP server, e.g. "http://127.0.0.1:8091".
        timeout:        Request timeout in seconds (default 30).
        namespace:      Private namespace name for encrypted storage.
        namespace_key:  Secret key for the namespace (AES-256-GCM encryption).
        keypair:        Optional Bittensor keypair (bt.Keypair) to sign requests.
                        Required when the miner runs with REQUIRE_HOTKEY_SIG=true.
    """

    def __init__(
        self,
        miner_url: str = "http://127.0.0.1:8091",
        timeout: float = 30.0,
        namespace: str | None = None,
        namespace_key: str | None = None,
        encryption=None,   # HybridEncryption instance — takes priority over namespace_key
        keypair=None,      # bt.Keypair — optional signing keypair
    ) -> None:
        self.miner_url     = miner_url.rstrip("/")
        self.timeout       = timeout
        self.namespace     = namespace
        self.namespace_key = namespace_key
        self._keypair      = keypair
        # Encryption engine: hybrid takes priority over password-based
        if encryption is not None:
            self._enc = encryption
        elif namespace and namespace_key:
            from engram.sdk.encryption import NamespaceEncryption
            self._enc = NamespaceEncryption(namespace, namespace_key)
        else:
            self._enc = None

    @classmethod
    def from_subnet(
        cls,
        netuid: int = 450,
        network: str = "finney",
        timeout: float = 30.0,
        probe_timeout: float = 3.0,
        top_n: int = 5,
    ) -> "EngramClient":
        """
        Auto-discover the best available miner from the Bittensor metagraph.

        Queries the metagraph for registered axons, health-checks the top_n
        candidates in parallel, and returns a client pointed at the fastest
        responsive miner.

        Args:
            netuid:        Subnet UID to query (default 450).
            network:       Subtensor network — "finney", "test", or ws:// endpoint.
            timeout:       Request timeout for the returned client.
            probe_timeout: Timeout for each health probe during discovery.
            top_n:         Number of axons to probe (picks by incentive rank).

        Returns:
            An EngramClient pointed at the best available miner.

        Raises:
            RuntimeError: If bittensor is not installed or no miners are reachable.

        Example::

            client = EngramClient.from_subnet()
            cid = client.ingest("Hello from auto-discovered miner!")
        """
        try:
            import bittensor as bt
        except ImportError:
            raise RuntimeError(
                "Auto-discovery requires bittensor. Install it with:\n"
                "  pip install bittensor"
            )

        subtensor = bt.Subtensor(network=network)
        metagraph = subtensor.metagraph(netuid=netuid)

        # Rank axons by incentive (highest first), skip empty IPs
        candidates: list[tuple[float, str]] = []
        incentives = metagraph.I.tolist() if hasattr(metagraph, "I") else []
        for uid, axon in enumerate(metagraph.axons):
            ip = axon.ip
            port = axon.port
            if not ip or ip in ("0.0.0.0", "0") or not port:
                continue
            incentive = incentives[uid] if uid < len(incentives) else 0.0
            candidates.append((incentive, f"http://{ip}:{port}"))

        candidates.sort(reverse=True)
        urls_to_probe = [url for _, url in candidates[:top_n]]

        if not urls_to_probe:
            raise RuntimeError(
                f"No registered axons found on subnet {netuid} ({network}). "
                "Make sure miners are running and registered."
            )

        # Probe candidates concurrently, return the first that responds
        import concurrent.futures
        def _probe(url: str) -> tuple[str, bool]:
            try:
                c = cls(url, timeout=probe_timeout)
                c.health()
                return url, True
            except Exception:
                return url, False

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(urls_to_probe)) as pool:
            futures = {pool.submit(_probe, url): url for url in urls_to_probe}
            winner: str | None = None
            for fut in concurrent.futures.as_completed(futures):
                url, ok = fut.result()
                if ok and winner is None:
                    winner = url

        if winner is None:
            raise RuntimeError(
                f"Probed {len(urls_to_probe)} miners on subnet {netuid} but none responded. "
                "The network may be starting up — try again in a moment."
            )

        return cls(winner, timeout=timeout)

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
        if self._enc:
            # Private namespace: encrypt text + metadata client-side, send raw embedding.
            # The miner never sees the original text — only the float vector + ciphertext.
            from engram.miner.embedder import get_embedder
            embedding = get_embedder().embed(text).tolist()
            enc_blob  = self._enc.encrypt_payload(text, metadata or {})
            payload: dict[str, Any] = {
                "raw_embedding": embedding,
                "metadata": {"_enc": enc_blob},
                "namespace":     self.namespace,
                "namespace_key": self.namespace_key,
            }
        else:
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
        payload: dict[str, Any] = {"raw_embedding": embedding, "metadata": metadata or {}}
        if self.namespace:
            payload["namespace"]     = self.namespace
            payload["namespace_key"] = self.namespace_key
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
        if self._enc:
            # Private namespace: compute query embedding locally, search by vector.
            from engram.miner.embedder import get_embedder
            query_vector = get_embedder().embed(text).tolist()
            payload: dict[str, Any] = {
                "query_vector":  query_vector,
                "top_k":         top_k,
                "namespace":     self.namespace,
                "namespace_key": self.namespace_key,
            }
        else:
            payload = {"query_text": text, "top_k": top_k}

        data = self._post("QuerySynapse", payload)

        if data.get("error"):
            raise QueryError(data["error"])

        results = data.get("results") or []
        # Decrypt _enc metadata fields if this is a private namespace client
        if self._enc:
            results = self._enc.decrypt_results(results)
        return results

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
        # Sign if a keypair was supplied — required when miner has REQUIRE_HOTKEY_SIG=true
        if self._keypair is not None:
            from engram.miner.auth import sign_request
            payload = sign_request(self._keypair, endpoint, payload)
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
