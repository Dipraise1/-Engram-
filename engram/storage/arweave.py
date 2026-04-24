"""
Engram — Arweave permanent media storage (Python layer).

Mirrors engram-web/lib/arweave.ts so the full subnet (SDK, miner, CLI) can
upload raw media to Arweave, not just the Next.js web frontend.

Env vars:
  ARWEAVE_KEY  — JWK wallet JSON string
                 Generate: node -e "require('arweave').init({}).wallets.generate().then(k=>console.log(JSON.stringify(k)))"
  ARWEAVE_ENV  — "mainnet" (default) | "devnet"

Upload failures are non-fatal — callers catch ArweaveUnavailable and degrade
gracefully (text still stored in Engram; arweave_tx_id absent from metadata).

Requires:
  pip install arweave-python-client
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass

from loguru import logger


class ArweaveUnavailable(Exception):
    """Raised when Arweave is not configured or the upload fails."""


@dataclass
class ArweaveUploadResult:
    tx_id: str
    url: str
    content_cid: str
    size: int


_GATEWAY = os.getenv("ARWEAVE_ENV", "mainnet")
_GATEWAY_URL = "https://arweave.net"


def is_configured() -> bool:
    """Return True when ARWEAVE_KEY is present in the environment."""
    return bool(os.environ.get("ARWEAVE_KEY"))


def content_cid(data: bytes) -> str:
    """SHA-256 content identifier matching the web layer's contentCid()."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def upload(
    data: bytes,
    content_type: str,
    tags: dict[str, str] | None = None,
) -> ArweaveUploadResult:
    """
    Upload raw bytes to Arweave and return the transaction result.

    Args:
        data:         Raw bytes to store permanently.
        content_type: MIME type (e.g. "image/jpeg", "application/pdf").
        tags:         Optional Arweave tags — queryable via GraphQL.

    Returns:
        ArweaveUploadResult with tx_id, url, content_cid, size.

    Raises:
        ArweaveUnavailable: ARWEAVE_KEY not set, package missing, or upload failed.
    """
    try:
        import arweave as _ar  # arweave-python-client
    except ImportError:
        raise ArweaveUnavailable(
            "arweave-python-client not installed. Run: pip install arweave-python-client"
        )

    raw_key = os.environ.get("ARWEAVE_KEY")
    if not raw_key:
        raise ArweaveUnavailable("ARWEAVE_KEY env var not set")

    try:
        jwk = json.loads(raw_key)
    except json.JSONDecodeError as exc:
        raise ArweaveUnavailable("ARWEAVE_KEY is not valid JSON") from exc

    # arweave-python-client loads from a file path — write to an ephemeral temp file
    fd, tmp_path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(jwk, f)
        wallet = _ar.Wallet(tmp_path)
    finally:
        os.unlink(tmp_path)

    try:
        tx = _ar.Transaction(wallet, data=data)
        tx.add_tag("Content-Type", content_type)
        tx.add_tag("App-Name", "Engram")
        tx.add_tag("App-Version", "1.0")
        for k, v in (tags or {}).items():
            tx.add_tag(k[:128], v[:128])

        tx.sign()
        resp = tx.send()
    except Exception as exc:
        raise ArweaveUnavailable(f"Arweave transaction failed: {exc}") from exc

    if getattr(resp, "status_code", 200) not in (200, 202):
        raise ArweaveUnavailable(
            f"Arweave upload rejected: HTTP {resp.status_code}"
        )

    tx_id = tx.id
    url = f"{_GATEWAY_URL}/{tx_id}"
    cid = content_cid(data)

    logger.info(
        f"Arweave upload OK | tx={tx_id[:16]}… | {len(data):,} bytes | {content_type}"
    )

    return ArweaveUploadResult(tx_id=tx_id, url=url, content_cid=cid, size=len(data))


def try_upload(
    data: bytes,
    content_type: str,
    tags: dict[str, str] | None = None,
) -> ArweaveUploadResult | None:
    """
    Best-effort upload — returns None instead of raising on any failure.

    Use this in ingest paths where Arweave is supplementary:
      result = arweave.try_upload(pdf_bytes, "application/pdf", {"File-Name": name})
      if result:
          meta["arweave_tx_id"] = result.tx_id
    """
    if not is_configured():
        return None
    try:
        return upload(data, content_type, tags)
    except ArweaveUnavailable as exc:
        logger.warning(f"Arweave upload skipped (non-fatal): {exc}")
        return None
    except Exception as exc:
        logger.warning(f"Arweave upload failed (non-fatal): {exc}")
        return None
