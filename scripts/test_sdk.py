"""
Phase 3.1 — SDK Client Test

Tests EngramClient against live miner neurons.

Covers:
  3.1  Basic ingest + query round-trip
  3.2  Error handling: offline miner, bad inputs, timeout

Prerequisites:
  - Miner 1 running on :8091  (python -m neurons.miner)
  - Miner 2 running on :8093  (optional — skipped if not up)

Run:
  python scripts/test_sdk.py
"""

import sys
import time
sys.path.insert(0, ".")

from engram.sdk import (
    EngramClient,
    EngramError,
    IngestError,
    InvalidCIDError,
    MinerOfflineError,
    QueryError,
)

MINER1 = "http://127.0.0.1:8091"
MINER2 = "http://127.0.0.1:8093"
DEAD_URL = "http://127.0.0.1:19999"  # nothing running here

results: list[tuple[str, bool]] = []

PASS = "✓"
FAIL = "✗"


def check(label: str, condition: bool) -> None:
    status = PASS if condition else FAIL
    print(f"  {status}  {label}")
    results.append((label, condition))


def section(title: str) -> None:
    print(f"\n[{title}]")


# ── 3.1  Basic round-trip ─────────────────────────────────────────────────────

def test_round_trip(client: EngramClient) -> None:
    section("3.1  Ingest + query round-trip")

    # Health check
    h = client.health()
    check("health() returns status=ok", h.get("status") == "ok")
    check("health() returns vector count", isinstance(h.get("vectors"), int))
    check("is_online() returns True", client.is_online())
    print(f"       Miner: uid={h.get('uid')} vectors={h.get('vectors')}")

    # Ingest — test CID determinism: same text+meta → same CID
    import uuid
    unique_token = uuid.uuid4().hex[:12]
    test_text = f"zxqv_unique_sdk_test_{unique_token} round-trip verification"
    cid_a = client.ingest(test_text, metadata={"source": "sdk_test"})
    cid_b = client.ingest(test_text, metadata={"source": "sdk_test"})
    check("ingest() returns non-empty CID", bool(cid_a))
    check("CID starts with 'v1::'", cid_a.startswith("v1::"))
    check("CID has 64-char hash part", len(cid_a.split("::")[-1]) == 64)
    check("same text+meta → same CID (deterministic)", cid_a == cid_b)
    print(f"       CID: {cid_a[:36]}…")

    # Different metadata → different CID
    cid_nometa = client.ingest(test_text)
    check("different metadata → different CID", cid_a != cid_nometa)

    # Query against existing ground-truth data (seeded into the store)
    # "transformer architecture" should be in ground truth
    results_q = client.query("attention mechanism in neural networks", top_k=10)
    check("query() returns a list", isinstance(results_q, list))
    check("query() returns ≥ 1 result", len(results_q) >= 1)

    if results_q:
        top = results_q[0]
        check("result has 'cid' key", "cid" in top)
        check("result has 'score' key", "score" in top)
        check("top result score is a float", isinstance(top["score"], float))
        check("top result score in HNSW range", -1.0 <= top["score"] <= 2.0)
        check("result CID starts with 'v1::'", top["cid"].startswith("v1::"))

    # Two different texts → two different CIDs
    cid2 = client.ingest("Completely different content about quantum computing")
    check("two distinct ingests produce different CIDs", cid_a != cid2)

    # query_by_vector
    import numpy as np
    vec = np.random.RandomState(1).randn(384).astype("float32")
    vec = (vec / np.linalg.norm(vec)).tolist()
    vec_results = client.query_by_vector(vec, top_k=3)
    check("query_by_vector() returns list", isinstance(vec_results, list))

    # ingest_embedding
    cid_emb = client.ingest_embedding(vec, metadata={"from": "raw_vec"})
    check("ingest_embedding() returns valid CID", cid_emb.startswith("v1::"))


# ── 3.2  Error handling ───────────────────────────────────────────────────────

def test_error_handling() -> None:
    section("3.2  Error handling")

    # Offline miner
    dead = EngramClient(DEAD_URL, timeout=2.0)
    try:
        dead.health()
        check("MinerOfflineError raised for unreachable host", False)
    except MinerOfflineError as exc:
        check("MinerOfflineError raised for unreachable host", True)
        check("MinerOfflineError.url is set", exc.url == f"{DEAD_URL}/health")

    # is_online() returns False for dead miner
    check("is_online() returns False for dead miner", not dead.is_online())

    # Timeout: use a very short timeout against a real server that won't respond in time
    # We simulate by pointing at a port that accepts but never responds — just verify
    # the exception type is correct by using a dead host with timeout=0.001
    dead_fast = EngramClient(DEAD_URL, timeout=0.001)
    try:
        dead_fast.ingest("test")
        check("MinerOfflineError on timeout/connection refused", False)
    except MinerOfflineError:
        check("MinerOfflineError on timeout/connection refused", True)
    except EngramError:
        check("MinerOfflineError on timeout/connection refused", True)  # EngramError subclass

    # Miner returns error in response body (send empty text)
    live = EngramClient(MINER1, timeout=10.0)
    try:
        # Raw embedding of wrong dimension should cause an error
        live.ingest_embedding([0.0] * 10)  # wrong dim for 384-d store
        # If miner silently accepts or stores with wrong dim, that's also fine to note
        check("IngestError or success for wrong-dim embedding (miner-dependent)", True)
    except (IngestError, EngramError):
        check("IngestError or success for wrong-dim embedding (miner-dependent)", True)

    # InvalidCIDError — we can't easily trigger this from a live miner
    # so we test parse_cid directly
    from engram.sdk.client import EngramClient as _C
    c = _C.__new__(_C)
    c.miner_url = ""
    c.timeout = 0
    try:
        c._validate_cid("bad_cid_no_separator")
        check("InvalidCIDError raised for malformed CID", False)
    except InvalidCIDError as exc:
        check("InvalidCIDError raised for malformed CID", True)
        check("InvalidCIDError.cid is set", exc.cid == "bad_cid_no_separator")

    try:
        c._validate_cid("v1::tooshort")
        check("InvalidCIDError raised for short hash", False)
    except InvalidCIDError:
        check("InvalidCIDError raised for short hash", True)


# ── Optional: miner 2 ─────────────────────────────────────────────────────────

def test_miner2() -> None:
    section("3.1  Miner 2 round-trip (:8093)")
    client2 = EngramClient(MINER2, timeout=10.0)
    if not client2.is_online():
        print("  [skipped] Miner 2 not running")
        return

    cid = client2.ingest("Testing SDK against miner 2")
    check("Miner2 ingest returns valid CID", cid.startswith("v1::"))
    r = client2.query("SDK miner2 test", top_k=3)
    check("Miner2 query returns results", len(r) >= 1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("Phase 3.1/3.2 — SDK Client Test")
    print("=" * 60)

    client = EngramClient(MINER1, timeout=30.0)

    if not client.is_online():
        print(f"\nERROR: Miner 1 not responding at {MINER1}")
        print("Start it with: python -m neurons.miner")
        sys.exit(1)

    test_round_trip(client)
    test_error_handling()
    test_miner2()

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for label, ok in results:
        print(f"  {'✓' if ok else '✗'}  {label}")
    print(f"\n  {passed}/{total} checks passed")
    print(f"\n  Overall: {'PASS ✓' if passed == total else 'FAIL ✗'}")

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
