"""Engram SDK — Exception hierarchy."""


class EngramError(Exception):
    """Base class for all Engram SDK errors."""


class MinerOfflineError(EngramError):
    """Raised when the miner cannot be reached (connection refused, timeout)."""

    def __init__(self, url: str, cause: Exception | None = None) -> None:
        self.url = url
        self.cause = cause
        super().__init__(f"Miner unreachable at {url}: {cause}")


class IngestError(EngramError):
    """Raised when the miner returns an error on ingest."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Ingest failed: {message}")


class QueryError(EngramError):
    """Raised when the miner returns an error on query."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Query failed: {message}")


class InvalidCIDError(EngramError):
    """Raised when a CID returned by the miner fails validation."""

    def __init__(self, cid: str) -> None:
        self.cid = cid
        super().__init__(f"Miner returned invalid CID: {cid!r}")
