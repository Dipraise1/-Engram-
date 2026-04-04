"""
Engram Miner — Prometheus Metrics

Exposes key operational metrics for monitoring.

Metrics:
  engram_ingest_total          — total ingest requests (labels: status=ok|error|rate_limited)
  engram_ingest_duration_ms    — ingest latency histogram (ms)
  engram_query_total           — total query requests (labels: status=ok|error)
  engram_query_duration_ms     — query latency histogram (ms)
  engram_vectors_stored        — current vector count in store
  engram_proof_total           — storage proof challenges (labels: result=pass|fail|expired)
  engram_proof_success_rate    — rolling success rate (gauge)
  engram_score                 — last validator score received (gauge)

Usage in miner.py:
  from engram.miner.metrics import METRICS
  METRICS.ingest_total.labels(status="ok").inc()
  with METRICS.ingest_duration.time(): ...
"""

from __future__ import annotations

try:
    from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry

    REGISTRY = CollectorRegistry()

    class _Metrics:
        def __init__(self) -> None:
            self.ingest_total = Counter(
                "engram_ingest_total",
                "Total ingest requests",
                ["status"],          # ok | error | rate_limited | low_stake
                registry=REGISTRY,
            )
            self.ingest_duration = Histogram(
                "engram_ingest_duration_ms",
                "Ingest request latency in milliseconds",
                buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500],
                registry=REGISTRY,
            )
            self.query_total = Counter(
                "engram_query_total",
                "Total query requests",
                ["status"],          # ok | error
                registry=REGISTRY,
            )
            self.query_duration = Histogram(
                "engram_query_duration_ms",
                "Query request latency in milliseconds",
                buckets=[1, 5, 10, 25, 50, 100, 250, 500],
                registry=REGISTRY,
            )
            self.vectors_stored = Gauge(
                "engram_vectors_stored",
                "Current number of vectors in the store",
                registry=REGISTRY,
            )
            self.proof_total = Counter(
                "engram_proof_total",
                "Storage proof challenge results",
                ["result"],          # pass | fail | expired
                registry=REGISTRY,
            )
            self.proof_success_rate = Gauge(
                "engram_proof_success_rate",
                "Rolling storage proof success rate (0–1)",
                registry=REGISTRY,
            )
            self.score = Gauge(
                "engram_score",
                "Last composite score received from validator",
                registry=REGISTRY,
            )
            self.peers_online = Gauge(
                "engram_peers_online",
                "Number of peers in the DHT routing table",
                registry=REGISTRY,
            )

    METRICS = _Metrics()
    AVAILABLE = True

except ImportError:
    AVAILABLE = False

    class _NoopMetric:
        def labels(self, **_): return self
        def inc(self, *_): pass
        def set(self, *_): pass
        def observe(self, *_): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def time(self): return self

    class _Metrics:  # type: ignore[no-redef]
        def __getattr__(self, _): return _NoopMetric()

    METRICS = _Metrics()


def generate_latest() -> bytes:
    """Return Prometheus text format metrics."""
    if not AVAILABLE:
        return b"# prometheus_client not installed\n"
    from prometheus_client import generate_latest as _gen
    return _gen(REGISTRY)
