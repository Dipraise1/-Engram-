"""
Phase 3.3 — JSONL Batch Ingest Test

Tests:
  - EngramClient ingests a JSONL file via batch_ingest()
  - Throughput measurement (records/sec)
  - Duplicate CID deduplication
  - Error tolerance (bad records skipped gracefully)

Run:
  python scripts/test_batch_ingest.py
"""

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, ".")
from engram.sdk import EngramClient, IngestError, MinerOfflineError

MINER = "http://127.0.0.1:8091"

results: list[tuple[str, bool]] = []


def check(label: str, condition: bool) -> None:
    status = "✓" if condition else "✗"
    print(f"  {status}  {label}")
    results.append((label, condition))


def make_jsonl(records: list[dict]) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False)
    for r in records:
        tmp.write(json.dumps(r) + "\n")
    tmp.close()
    return Path(tmp.name)


def main() -> None:
    print("=" * 60)
    print("Phase 3.3 — JSONL Batch Ingest Test")
    print("=" * 60)

    client = EngramClient(MINER, timeout=30.0)
    if not client.is_online():
        print(f"\nERROR: Miner not responding at {MINER}")
        sys.exit(1)

    h = client.health()
    print(f"\nMiner: uid={h['uid']} vectors={h['vectors']}")

    # ── [1] Basic batch ingest ────────────────────────────────────────────────
    print("\n[1] Basic JSONL batch (10 records)")
    batch = [
        {"text": f"Batch ingest test record {i} — neural networks and machine learning", "metadata": {"idx": i, "source": "batch_test"}}
        for i in range(10)
    ]
    jsonl_file = make_jsonl(batch)

    t0 = time.perf_counter()
    cids = client.batch_ingest_file(jsonl_file)
    elapsed = time.perf_counter() - t0

    check("batch_ingest_file() returns list of CIDs", isinstance(cids, list))
    check("all 10 records ingested", len(cids) == 10)
    check("all CIDs are valid v1:: format", all(c.startswith("v1::") and len(c.split("::")[-1]) == 64 for c in cids))
    check("all CIDs distinct (different texts)", len(set(cids)) == 10)

    throughput = len(cids) / elapsed
    print(f"       Throughput: {throughput:.1f} records/sec ({elapsed*1000:.0f}ms total)")
    check("throughput > 1 record/sec", throughput > 1.0)

    # ── [2] Deduplication ─────────────────────────────────────────────────────
    print("\n[2] Duplicate deduplication")
    dup_batch = [
        {"text": "dedup test: this exact text ingested twice"},
        {"text": "dedup test: this exact text ingested twice"},  # duplicate
        {"text": "dedup test: this is a different text"},
    ]
    dup_file = make_jsonl(dup_batch)
    dup_cids = client.batch_ingest_file(dup_file)

    check("3 records → 3 CIDs returned", len(dup_cids) == 3)
    check("duplicate texts produce same CID", dup_cids[0] == dup_cids[1])
    check("different text produces different CID", dup_cids[0] != dup_cids[2])

    # ── [3] Error tolerance ───────────────────────────────────────────────────
    print("\n[3] Error tolerance (bad records mixed in)")
    mixed_batch = [
        {"text": "good record one — deep learning fundamentals"},
        {"no_text_field": "this record has no text"},          # bad — no text
        {"text": "good record two — convolutional neural networks"},
        {"text": ""},                                           # bad — empty text
        {"text": "good record three — recurrent networks"},
    ]
    mixed_file = make_jsonl(mixed_batch)
    mixed_cids, errors = client.batch_ingest_file(mixed_file, return_errors=True)

    check("good records returned (≥ 3 CIDs)", len(mixed_cids) >= 3)
    check("bad records captured as errors", len(errors) >= 1)
    check("no exception raised for bad records", True)  # we got here

    print(f"       {len(mixed_cids)} ingested, {len(errors)} errors")
    for e in errors:
        print(f"         error: {e}")

    # ── [4] Larger batch throughput ───────────────────────────────────────────
    print("\n[4] 50-record batch throughput")
    import numpy as np
    rng = np.random.RandomState(99)
    large_texts = [
        {
            "text": f"Engram throughput test {i}: "
                    + " ".join(f"word{rng.randint(1000)}" for _ in range(20)),
            "metadata": {"batch": "throughput_test", "i": i},
        }
        for i in range(50)
    ]
    large_file = make_jsonl(large_texts)

    t0 = time.perf_counter()
    large_cids = client.batch_ingest_file(large_file)
    elapsed50 = time.perf_counter() - t0

    tput50 = len(large_cids) / elapsed50
    print(f"       {len(large_cids)} records in {elapsed50*1000:.0f}ms → {tput50:.1f} rec/sec")
    check(f"50-record batch ingested ({len(large_cids)}/50)", len(large_cids) == 50)
    check("throughput > 2 rec/sec for 50 records", tput50 > 2.0)

    # ── Summary ───────────────────────────────────────────────────────────────
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
