"""
Phase 5.2 — CID Generation Benchmark: Python vs Rust

Measures the speedup from using engram_core (Rust) over the Python hashlib
implementation for large batch CID generation.

Run:
  python scripts/benchmark_cid.py
"""

import sys
import time
import numpy as np

sys.path.insert(0, ".")

BATCH_SIZES = [100, 1_000, 10_000]
DIM = 384
RUNS = 3


def bench(fn, embeddings: list, label: str) -> float:
    """Return median time per record in microseconds."""
    times = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        for emb in embeddings:
            fn(emb)
        times.append(time.perf_counter() - t0)
    median_total = sorted(times)[1]
    us_per_record = (median_total / len(embeddings)) * 1e6
    rps = len(embeddings) / median_total
    print(f"  {label:20s}  {us_per_record:7.2f} µs/rec  {rps:>10,.0f} rec/sec")
    return us_per_record


def main() -> None:
    print("=" * 60)
    print("Phase 5.2 — CID Generation Benchmark (Python vs Rust)")
    print("=" * 60)

    try:
        import engram_core
        rust_available = True
    except ImportError:
        rust_available = False
        print("ERROR: engram_core not built. Run: cd engram-core && maturin develop --release")
        sys.exit(1)

    from engram.cid import generate_cid as py_generate_cid

    rng = np.random.RandomState(42)

    for n in BATCH_SIZES:
        print(f"\nBatch size: {n:,} vectors (dim={DIM})")
        embeddings = [
            rng.randn(DIM).astype(np.float32)
            for _ in range(n)
        ]

        # Python implementation
        def py_fn(emb):
            return py_generate_cid(emb, metadata={})

        # Rust implementation
        def rust_fn(emb):
            return engram_core.generate_cid(emb.tolist(), {}, "v1")

        py_us = bench(py_fn, embeddings, "Python (hashlib)")
        rs_us = bench(rust_fn, embeddings, "Rust (engram_core)")
        speedup = py_us / rs_us
        print(f"  {'Speedup':20s}  {speedup:7.1f}×")

    # Cross-validate: same input → same CID
    print("\n[Cross-validation]")
    test_emb = rng.randn(DIM).astype(np.float32)
    cid_py = py_generate_cid(test_emb, metadata={})
    cid_rs = engram_core.generate_cid(test_emb.tolist(), {}, "v1")
    match = cid_py == cid_rs
    print(f"  Python CID: {cid_py[:40]}…")
    print(f"  Rust CID:   {cid_rs[:40]}…")
    print(f"  Match: {'✓' if match else '✗'}")

    if not match:
        print("\nERROR: CID mismatch — Python and Rust implementations diverged!")
        sys.exit(1)
    else:
        print("\nAll checks passed ✓")


if __name__ == "__main__":
    main()
