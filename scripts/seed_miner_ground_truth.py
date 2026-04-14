"""
Engram — Seed Miner with Ground Truth Vectors

Reads data/ground_truth.jsonl and POSTs each entry to the miner via
raw_embedding so the miner stores the EXACT same f32 embeddings
(and thus the same CIDs) as the validator's ground truth.

This is required for storage proof challenges to pass: the validator
verifies proofs using ground_truth embeddings, and the miner must have
those exact embeddings stored under the same CIDs.

Usage:
    python scripts/seed_miner_ground_truth.py [--miner-url http://localhost:8091]
    python scripts/seed_miner_ground_truth.py --miner-url http://72.62.2.34:8091
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")


def seed(miner_url: str, ground_truth_path: Path, dry_run: bool = False, delay: float = 0.0) -> None:
    if not ground_truth_path.exists():
        print(f"ERROR: Ground truth file not found: {ground_truth_path}", file=sys.stderr)
        sys.exit(1)

    entries = []
    with ground_truth_path.open() as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"  WARN line {lineno}: {exc}", file=sys.stderr)
                continue
            if "cid" not in obj or "embedding" not in obj:
                print(f"  WARN line {lineno}: missing cid or embedding", file=sys.stderr)
                continue
            entries.append(obj)

    print(f"Loaded {len(entries)} ground truth entries from {ground_truth_path}")
    print(f"Target miner: {miner_url}")
    if dry_run:
        print("DRY RUN — no requests will be sent")
        return

    ok = 0
    mismatch = 0
    errors = 0

    # Default: pace to stay under the miner's 100 req/60s rate limit.
    # Use --delay 0 to disable if seeding from localhost or with a permissive limit.
    if delay == 0.0:
        delay = 0.7  # ~85 req/min, safely under 100/min default limit

    import time as _time
    import urllib.error as _urlerr

    def _post_entry(payload_bytes: bytes, retries: int = 5) -> dict:
        """POST with exponential backoff on 429 rate limit responses."""
        url = f"{miner_url}/IngestSynapse"
        wait = 62  # wait just over 60s to let the sliding window reset
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    url, data=payload_bytes,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read())
            except _urlerr.HTTPError as exc:
                if exc.code == 429 and attempt < retries - 1:
                    print(f"    429 rate limit — waiting {wait}s …", flush=True)
                    _time.sleep(wait)
                    continue
                raise
        raise RuntimeError("max retries exceeded")

    for i, entry in enumerate(entries):
        cid_expected = entry["cid"]
        embedding = entry["embedding"]
        metadata = entry.get("metadata", {})

        payload = json.dumps({
            "raw_embedding": embedding,
            "metadata": metadata,
        }).encode()

        try:
            data = _post_entry(payload)
        except Exception as exc:
            print(f"  [{i+1}/{len(entries)}] ERROR posting to miner: {exc}")
            errors += 1
            continue

        if data.get("error"):
            print(f"  [{i+1}/{len(entries)}] Miner error: {data['error']}")
            errors += 1
            continue

        cid_returned = data.get("cid", "")
        if delay > 0:
            _time.sleep(delay)

        if cid_returned == cid_expected:
            ok += 1
            if (i + 1) % 25 == 0 or i == 0:
                print(f"  [{i+1}/{len(entries)}] OK  cid={cid_returned[:20]}…")
        else:
            mismatch += 1
            print(
                f"  [{i+1}/{len(entries)}] CID MISMATCH!\n"
                f"    expected: {cid_expected}\n"
                f"    returned: {cid_returned}\n"
                "    This means the miner used a different embedding — "
                "check EMBEDDING_DIM matches between validator and miner."
            )

    print(f"\nDone — ok={ok}  mismatch={mismatch}  errors={errors}")
    if mismatch > 0:
        print(
            "\nWARNING: CID mismatches mean the miner computed different CIDs from the same\n"
            "raw_embedding. This should NOT happen — investigate the CID generation path."
        )
    if errors > 0:
        print(
            "\nSome entries failed to ingest. Re-run to retry; ingest is idempotent."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed miner with ground truth embeddings.")
    parser.add_argument(
        "--miner-url",
        default="http://72.62.2.34:8091",
        help="Base URL of the miner (default: http://72.62.2.34:8091)",
    )
    parser.add_argument(
        "--ground-truth",
        default="data/ground_truth.jsonl",
        help="Path to ground truth JSONL file (default: data/ground_truth.jsonl)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count entries without sending any requests",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds between requests (default: 0.7 to stay under 100 req/min rate limit). "
             "Use --delay 0 when seeding from the same host as the miner.",
    )
    args = parser.parse_args()

    seed(
        miner_url=args.miner_url.rstrip("/"),
        ground_truth_path=Path(args.ground_truth),
        dry_run=args.dry_run,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
