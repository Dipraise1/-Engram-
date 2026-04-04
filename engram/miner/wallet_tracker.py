"""
Engram Miner — Wallet Activity Tracker

Persists per-hotkey ingest/query counts and CID history to a JSON file
so the CLI `engram wallet-stats` command can report on wallet activity.

File format (data/wallet_stats.json):
{
  "<hotkey_ss58>": {
    "ingest_count": 42,
    "query_count": 17,
    "last_seen": 1735000000.0,
    "cids": ["v1::abc...", ...]   # capped at MAX_CID_HISTORY per wallet
  }
}
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import Lock

MAX_CID_HISTORY = int(os.getenv("WALLET_TRACKER_MAX_CIDS", "200"))
_DEFAULT_PATH = Path(os.getenv("WALLET_STATS_PATH", "data/wallet_stats.json"))


class WalletTracker:
    """
    Thread-safe, file-backed per-hotkey activity tracker.

    Args:
        path: Path to the JSON persistence file.
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = path
        self._lock = Lock()
        self._data: dict = self._load()

    # ── Public API ─────────────────────────────────────────────────────────────

    def record_ingest(self, hotkey: str, cid: str | None = None) -> None:
        """Increment ingest count; optionally append the resulting CID."""
        with self._lock:
            entry = self._entry(hotkey)
            entry["ingest_count"] += 1
            entry["last_seen"] = time.time()
            if cid:
                cids = entry["cids"]
                if cid not in cids:
                    cids.append(cid)
                    if len(cids) > MAX_CID_HISTORY:
                        entry["cids"] = cids[-MAX_CID_HISTORY:]
            self._flush()

    def record_query(self, hotkey: str) -> None:
        """Increment query count."""
        with self._lock:
            entry = self._entry(hotkey)
            entry["query_count"] += 1
            entry["last_seen"] = time.time()
            self._flush()

    def get_stats(self, hotkey: str) -> dict:
        """Return stats for a single hotkey (empty defaults if unknown)."""
        with self._lock:
            return dict(self._data.get(hotkey, self._blank()))

    def all_hotkeys(self) -> list[str]:
        """Return all tracked hotkeys sorted by last_seen descending."""
        with self._lock:
            return sorted(
                self._data.keys(),
                key=lambda k: self._data[k].get("last_seen", 0),
                reverse=True,
            )

    def summary(self) -> list[dict]:
        """Return a list of {hotkey, ingest_count, query_count, last_seen} sorted by activity."""
        with self._lock:
            rows = []
            for hotkey, entry in self._data.items():
                rows.append({
                    "hotkey": hotkey,
                    "ingest_count": entry["ingest_count"],
                    "query_count": entry["query_count"],
                    "last_seen": entry["last_seen"],
                    "cid_count": len(entry["cids"]),
                })
            return sorted(rows, key=lambda r: r["last_seen"], reverse=True)

    # ── Private ───────────────────────────────────────────────────────────────

    def _entry(self, hotkey: str) -> dict:
        if hotkey not in self._data:
            self._data[hotkey] = self._blank()
        return self._data[hotkey]

    @staticmethod
    def _blank() -> dict:
        return {"ingest_count": 0, "query_count": 0, "last_seen": 0.0, "cids": []}

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2),
            encoding="utf-8",
        )
