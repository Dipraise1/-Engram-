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

import base64
import hashlib
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
        filter: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Semantic search over the miner's stored embeddings.

        Args:
            text:   Query text to search for.
            top_k:  Maximum number of results to return.
            filter: Optional metadata filter — only results whose metadata
                    contains ALL specified key/value pairs are returned.
                    e.g. ``filter={"user_id": "u_123", "type": "image"}``

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

        if filter:
            payload["filter"] = filter

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

    def ingest_image(
        self,
        source: str | Path | bytes,
        *,
        xai_api_key: str,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Describe an image with Grok Vision and store the description as a memory.

        The image is described by the xAI Grok Vision model. The resulting text
        description is embedded and stored on the miner. The raw image bytes are
        **not** sent to the miner — only the semantic description is stored.

        Args:
            source:      File path, Path object, or raw image bytes.
            xai_api_key: Your xAI API key (get one at console.x.ai).
            mime_type:   MIME type of the image (e.g. "image/jpeg"). Auto-detected
                         from file extension if source is a path and mime_type is None.
            metadata:    Optional extra metadata stored alongside the vector.

        Returns:
            dict with keys:
                "cid"         — Engram CID (semantic address for search)
                "description" — AI-generated description of the image
                "content_cid" — sha256 of raw image bytes (integrity check)
                "filename"    — source filename if a path was provided

        Raises:
            MinerOfflineError:  Miner is unreachable.
            IngestError:        Miner rejected the request.
            RuntimeError:       Grok Vision API call failed.

        Example::

            result = client.ingest_image(
                "photo.jpg",
                xai_api_key="xai-...",
            )
            print(result["cid"])         # v1::a3f2b1...
            print(result["description"]) # "A photograph of..."
        """
        # ── Read bytes + detect mime type ──────────────────────────────────
        filename: str | None = None
        if isinstance(source, (str, Path)):
            path = Path(source)
            filename = path.name
            image_bytes = path.read_bytes()
            if mime_type is None:
                ext = path.suffix.lower()
                mime_type = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".gif": "image/gif",
                    ".webp": "image/webp",
                }.get(ext, "image/png")
        else:
            image_bytes = source
            if mime_type is None:
                mime_type = "image/png"

        content_cid = "sha256:" + hashlib.sha256(image_bytes).hexdigest()
        b64 = base64.b64encode(image_bytes).decode("ascii")

        # ── Arweave permanent storage ──────────────────────────────────────
        # Encrypt before upload when operating in a private namespace so
        # gateway operators cannot read the raw media (ATLAS AML.T0035).
        from engram.storage.arweave import try_upload as _arweave_upload
        _upload_bytes = (
            self._enc.encrypt_raw(image_bytes) if self._enc is not None else image_bytes
        )
        _arweave = _arweave_upload(
            _upload_bytes,
            "application/octet-stream" if self._enc is not None else mime_type,
            {
                "Content-Hash": content_cid,
                **({"File-Name": filename} if filename else {}),
                "Encrypted": "true" if self._enc is not None else "false",
                "Content-Source": "engram-sdk",
            },
        )

        # ── Call Grok Vision ───────────────────────────────────────────────
        description = self._describe_image_grok(b64, mime_type, xai_api_key)

        # ── Build metadata ─────────────────────────────────────────────────
        meta: dict[str, Any] = {
            "type": "image",
            "content_cid": content_cid,
            **({"source": filename} if filename else {}),
            **({"arweave_tx_id": _arweave.tx_id, "arweave_url": _arweave.url} if _arweave else {}),
            **(metadata or {}),
        }
        # Store first 500 chars of description so CID page can show it
        meta["text"] = description[:500]

        cid = self.ingest(description, metadata=meta)

        return {
            "cid": cid,
            "description": description,
            "content_cid": content_cid,
            "filename": filename,
            "arweave_tx_id": _arweave.tx_id if _arweave else None,
            "arweave_url": _arweave.url if _arweave else None,
        }

    def ingest_pdf(
        self,
        source: str | Path | bytes,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Extract text from a PDF and store it as a memory.

        Requires the ``pypdf`` package::

            pip install pypdf

        Args:
            source:   File path, Path object, or raw PDF bytes.
            metadata: Optional extra metadata.

        Returns:
            dict with keys:
                "cid"         — Engram CID
                "pages"       — number of pages extracted
                "chars"       — number of characters stored
                "content_cid" — sha256 of the raw PDF bytes
                "filename"    — source filename if a path was provided

        Raises:
            MinerOfflineError:  Miner is unreachable.
            IngestError:        Miner rejected the request.
            ImportError:        pypdf is not installed.
            ValueError:         PDF has no extractable text (image-only PDF).

        Example::

            result = client.ingest_pdf("research_paper.pdf")
            print(result["cid"])    # v1::...
            print(result["pages"])  # 12
        """
        try:
            import pypdf  # type: ignore
        except ImportError:
            raise ImportError(
                "ingest_pdf() requires pypdf. Install it with:\n"
                "  pip install pypdf"
            )

        # ── Read bytes ─────────────────────────────────────────────────────
        filename: str | None = None
        if isinstance(source, (str, Path)):
            path = Path(source)
            filename = path.name
            pdf_bytes = path.read_bytes()
        else:
            pdf_bytes = source

        content_cid = "sha256:" + hashlib.sha256(pdf_bytes).hexdigest()

        # ── Arweave permanent storage ──────────────────────────────────────
        from engram.storage.arweave import try_upload as _arweave_upload
        _upload_bytes = (
            self._enc.encrypt_raw(pdf_bytes) if self._enc is not None else pdf_bytes
        )
        _arweave = _arweave_upload(
            _upload_bytes,
            "application/octet-stream" if self._enc is not None else "application/pdf",
            {
                "Content-Hash": content_cid,
                **({"File-Name": filename} if filename else {}),
                "Encrypted": "true" if self._enc is not None else "false",
                "Content-Source": "engram-sdk",
            },
        )

        # ── Extract text ───────────────────────────────────────────────────
        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = len(reader.pages)
        raw = " ".join(
            (page.extract_text() or "") for page in reader.pages
        )
        text = " ".join(raw.split()).strip()

        if not text:
            raise ValueError(
                "PDF appears to be empty or image-only. "
                "For scanned PDFs, run OCR first or use ingest_image() per page."
            )

        # ── Build metadata + ingest ────────────────────────────────────────
        MAX_CHARS = 8192
        meta: dict[str, Any] = {
            "type": "pdf",
            "pages": str(pages),
            "content_cid": content_cid,
            "text": text[:500],
            **({"source": filename} if filename else {}),
            **({"arweave_tx_id": _arweave.tx_id, "arweave_url": _arweave.url} if _arweave else {}),
            **(metadata or {}),
        }

        cid = self.ingest(text[:MAX_CHARS], metadata=meta)

        return {
            "cid": cid,
            "pages": pages,
            "chars": len(text),
            "content_cid": content_cid,
            "filename": filename,
            "arweave_tx_id": _arweave.tx_id if _arweave else None,
            "arweave_url": _arweave.url if _arweave else None,
        }

    def get(self, cid: str) -> dict[str, Any]:
        """
        Retrieve the metadata for a stored memory by CID.

        Args:
            cid: The content identifier returned by a previous ingest call.

        Returns:
            dict with keys ``cid`` and ``metadata``.

        Raises:
            MinerOfflineError: Miner is unreachable.
            KeyError: CID not found on this miner (404).

        Example::

            record = client.get("v1::a3f2b1...")
            print(record["metadata"]["text"])   # stored text snippet
            print(record["metadata"]["type"])   # "image", "pdf", or absent
        """
        import urllib.parse
        result = self._get(f"retrieve/{urllib.parse.quote(cid, safe='')}")
        if result.get("error"):
            raise KeyError(f"CID not found: {cid}")
        return result

    def delete(self, cid: str) -> bool:
        """
        Permanently delete a stored memory by CID.

        Args:
            cid: The content identifier to delete.

        Returns:
            True if deleted, False if not found.

        Raises:
            MinerOfflineError: Miner is unreachable.

        Example::

            deleted = client.delete("v1::a3f2b1...")
            print(deleted)  # True
        """
        import urllib.parse
        url = f"{self.miner_url}/retrieve/{urllib.parse.quote(cid, safe='')}"
        try:
            req = urllib.request.Request(url, method="DELETE")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
                return data.get("deleted", False)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            raise EngramError(f"Delete failed: {exc}") from exc
        except (ConnectionRefusedError, socket.timeout) as exc:
            raise MinerOfflineError(url, exc) from exc
        except urllib.error.URLError as exc:
            raise EngramError(f"Delete request failed: {exc}") from exc

    def list(
        self,
        filter: dict[str, str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List stored memories, optionally filtered by metadata.

        All filter key/value pairs must match (AND semantics).
        Values are compared as strings.

        Args:
            filter: Metadata key/value pairs to match, e.g. ``{"user_id": "u_123"}``.
            limit:  Max records to return (default 50, max 200).
            offset: Skip N records for pagination (default 0).

        Returns:
            List of dicts, each with ``cid`` and ``metadata`` keys.

        Example::

            # All memories for a specific user
            records = client.list(filter={"user_id": "u_123"})
            for r in records:
                print(r["cid"], r["metadata"].get("type"))

            # Paginate
            page2 = client.list(limit=50, offset=50)
        """
        payload: dict[str, Any] = {"limit": limit, "offset": offset}
        if filter:
            payload["filter"] = filter
        if self.namespace:
            payload["namespace"] = self.namespace
        data = self._post("list", payload)
        return data.get("records") or []

    def ingest_url(
        self,
        url: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Fetch a URL, extract its text, and store it as a memory.

        Uses only stdlib (``urllib``, ``html.parser``) — no extra dependencies.

        Args:
            url:      The URL to fetch and store.
            metadata: Optional extra metadata. ``source`` defaults to the URL.

        Returns:
            dict with keys ``cid``, ``url``, ``title``, ``chars``.

        Raises:
            MinerOfflineError: Miner is unreachable.
            IngestError: Miner rejected the request.
            RuntimeError: URL fetch failed or page has no text content.

        Example::

            result = client.ingest_url("https://arxiv.org/abs/1706.03762")
            print(result["cid"])    # v1::...
            print(result["title"])  # "Attention Is All You Need"
        """
        import html.parser
        import urllib.request as _req

        class _TextExtractor(html.parser.HTMLParser):
            def __init__(self):
                super().__init__()
                self.text_parts: list[str] = []
                self.title: str = ""
                self._in_title = False
                self._skip_tags = {"script", "style", "nav", "footer", "header"}
                self._skip_depth = 0

            def handle_starttag(self, tag, attrs):
                if tag == "title":
                    self._in_title = True
                if tag in self._skip_tags:
                    self._skip_depth += 1

            def handle_endtag(self, tag):
                if tag == "title":
                    self._in_title = False
                if tag in self._skip_tags and self._skip_depth > 0:
                    self._skip_depth -= 1

            def handle_data(self, data):
                if self._in_title:
                    self.title += data
                elif self._skip_depth == 0:
                    stripped = data.strip()
                    if stripped:
                        self.text_parts.append(stripped)

        try:
            request = _req.Request(
                url,
                headers={"User-Agent": "EngramBot/1.0 (semantic-memory-indexer)"},
            )
            with _req.urlopen(request, timeout=15) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read()
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc

        if "text/html" not in content_type and "text/plain" not in content_type:
            raise RuntimeError(
                f"URL returned {content_type!r} — only text/html and text/plain are supported. "
                "For PDFs use ingest_pdf(), for images use ingest_image()."
            )

        charset = "utf-8"
        for part in content_type.split(";"):
            if "charset=" in part:
                charset = part.split("=", 1)[1].strip()
                break

        html_text = raw.decode(charset, errors="replace")

        if "text/plain" in content_type:
            text = " ".join(html_text.split())
            title = url
        else:
            parser = _TextExtractor()
            parser.feed(html_text)
            text = " ".join(parser.text_parts)
            title = parser.title.strip() or url

        text = " ".join(text.split())   # normalise whitespace
        if not text:
            raise RuntimeError(f"No text content found at {url}")

        # ── Arweave permanent archive of raw page bytes ────────────────────
        from engram.storage.arweave import try_upload as _arweave_upload
        _raw_mime = "text/html" if "text/html" in content_type else "text/plain"
        _arweave = _arweave_upload(
            raw,
            _raw_mime,
            {"Source-URL": url[:128], "Content-Source": "engram-sdk"},
        )

        MAX_CHARS = 8192
        meta: dict[str, Any] = {
            "source": url,
            "type": "url",
            "title": title[:256],
            "text": text[:500],
            **({"arweave_tx_id": _arweave.tx_id, "arweave_url": _arweave.url} if _arweave else {}),
            **(metadata or {}),
        }
        cid = self.ingest(text[:MAX_CHARS], metadata=meta)

        return {
            "cid": cid,
            "url": url,
            "title": title,
            "chars": len(text),
            "arweave_tx_id": _arweave.tx_id if _arweave else None,
            "arweave_url": _arweave.url if _arweave else None,
        }

    def ingest_conversation(
        self,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[str]:
        """
        Store a conversation (list of messages) as individual memories.

        Each message becomes its own CID, tagged with ``role``, ``session``,
        and ``ts`` (Unix timestamp) metadata so it can be filtered and
        retrieved later.

        Args:
            messages:   List of ``{"role": "user"|"assistant", "content": "..."}`` dicts.
            session_id: Optional session/conversation identifier stored as ``session`` metadata.
            metadata:   Optional extra metadata applied to every message.

        Returns:
            List of CIDs, one per message (in order).

        Example::

            cids = client.ingest_conversation(
                [
                    {"role": "user",      "content": "What is Bittensor?"},
                    {"role": "assistant", "content": "Bittensor is a decentralised ML network..."},
                ],
                session_id="conv_abc123",
            )
            # Later — retrieve context for this session
            results = client.query(
                "what did we discuss about Bittensor?",
                filter={"session": "conv_abc123"},
            )
        """
        import time as _time

        cids: list[str] = []
        for msg in messages:
            role    = str(msg.get("role", "user"))
            content = str(msg.get("content", "")).strip()
            if not content:
                continue

            meta: dict[str, Any] = {
                "role": role,
                "ts":   str(int(_time.time())),
                "text": content[:500],
                **({"session": session_id} if session_id else {}),
                **(metadata or {}),
            }
            cid = self.ingest(content, metadata=meta)
            cids.append(cid)

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

    def _describe_image_grok(self, b64: str, mime_type: str, api_key: str) -> str:
        """Call xAI Grok Vision to describe an image. Returns the description string."""
        payload = json.dumps({
            "model": "grok-2-vision-latest",
            "max_tokens": 1024,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64}",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Describe this image in detail. Extract any visible text verbatim. "
                            "Include layout, content, and context. Be thorough — this description "
                            "will be stored as a searchable memory."
                        ),
                    },
                ],
            }],
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.x.ai/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"Grok Vision API error {exc.code}: {body}") from exc
        except Exception as exc:
            raise RuntimeError(f"Grok Vision API request failed: {exc}") from exc

        description = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not description:
            raise RuntimeError("Grok Vision returned an empty description")
        return description

    def __repr__(self) -> str:
        return f"EngramClient(miner_url={self.miner_url!r}, timeout={self.timeout})"
