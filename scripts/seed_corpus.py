"""
Engram — Seed Corpus Script

Bootstraps the network with public corpora at launch.
Run this before mainnet to ensure the network has data from day one.

Usage:
    python scripts/seed_corpus.py --corpus wikipedia --limit 10000
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
z
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


def seed_wikipedia(limit: int, output_path: str) -> None:
    """Download Wikipedia summaries and write as JSONL for bulk ingest."""
    try:
        import wikipedia
    except ImportError:
        logger.error("Install wikipedia: pip install wikipedia-api")
        return

    logger.info(f"Seeding Wikipedia | limit={limit}")
    count = 0

    with open(output_path, "w") as f:
        # Sample random Wikipedia pages
        for _ in range(limit):
            try:
                page = wikipedia.random(pages=1)
                summary = wikipedia.summary(page, sentences=5)
                record = {
                    "text": summary,
                    "metadata": {"source": "wikipedia", "title": page},
                }
                f.write(json.dumps(record) + "\n")
                count += 1
                if count % 100 == 0:
                    logger.info(f"  {count}/{limit} pages seeded")
            except Exception as e:
                logger.warning(f"Skip: {e}")

    logger.success(f"Wikipedia seed complete: {count} records → {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Engram network with public corpora.")
    parser.add_argument("--corpus", choices=["wikipedia"], default="wikipedia")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output", default="./data/seed_corpus.jsonl")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    if args.corpus == "wikipedia":
        seed_wikipedia(limit=args.limit, output_path=args.output)


if __name__ == "__main__":
    main()
