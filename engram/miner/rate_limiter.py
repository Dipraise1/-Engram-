"""
Engram Miner — Per-hotkey Rate Limiter

Limits ingest requests per hotkey (or IP fallback) using a sliding window.
Configured via env vars:
  RATE_LIMIT_MAX_REQUESTS  — max ingest requests per window (default 100)
  RATE_LIMIT_WINDOW_SECS   — window duration in seconds (default 60)
"""

from __future__ import annotations

import os
import time
from collections import deque
from threading import Lock

from loguru import logger

MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))
WINDOW_SECS  = int(os.getenv("RATE_LIMIT_WINDOW_SECS", "60"))

# Evict stale keys every N seconds to prevent unbounded memory growth
_EVICTION_INTERVAL = 300


class RateLimiter:
    """
    Sliding window rate limiter keyed by hotkey or IP address.

    Tracks the timestamps of recent requests in a deque per key.
    A request is allowed if fewer than MAX_REQUESTS were made in the
    last WINDOW_SECS seconds.

    Stale keys (no requests in 2× the window) are evicted periodically
    to prevent unbounded memory growth from random/attacker-generated keys.
    """

    def __init__(
        self,
        max_requests: int = MAX_REQUESTS,
        window_secs: int = WINDOW_SECS,
    ) -> None:
        self.max_requests = max_requests
        self.window_secs  = window_secs
        self._windows: dict[str, deque[float]] = {}
        self._lock = Lock()
        self._last_eviction = time.time()

    def is_allowed(self, key: str) -> bool:
        """Return True if the key (hotkey or IP) is within its rate limit."""
        now = time.time()
        with self._lock:
            self._maybe_evict(now)
            window = self._windows.setdefault(key, deque())

            # Evict timestamps outside the sliding window
            cutoff = now - self.window_secs
            while window and window[0] < cutoff:
                window.popleft()

            if len(window) >= self.max_requests:
                logger.warning(
                    f"Rate limit exceeded | key={key[:16]}… | "
                    f"{len(window)}/{self.max_requests} req in {self.window_secs}s"
                )
                return False

            window.append(now)
            return True

    def check(self, key: str) -> None:
        """Raise ValueError if the key is rate-limited."""
        if not self.is_allowed(key):
            raise ValueError(
                f"Slow down — you've sent {self.max_requests} requests in the last "
                f"{self.window_secs}s. Wait a moment and try again."
            )

    def stats(self, key: str) -> dict:
        """Return current usage stats for a key."""
        now = time.time()
        with self._lock:
            window = self._windows.get(key, deque())
            cutoff = now - self.window_secs
            recent = sum(1 for t in window if t >= cutoff)
        return {
            "key": key,
            "requests_in_window": recent,
            "max_requests": self.max_requests,
            "window_secs": self.window_secs,
            "remaining": max(0, self.max_requests - recent),
        }

    def reset(self, key: str) -> None:
        """Clear rate limit state for a key (admin use)."""
        with self._lock:
            self._windows.pop(key, None)

    # ── Private ───────────────────────────────────────────────────────────────

    def _maybe_evict(self, now: float) -> None:
        """Evict keys with no recent activity to prevent memory exhaustion.
        Must be called with self._lock held."""
        if now - self._last_eviction < _EVICTION_INTERVAL:
            return
        stale_cutoff = now - self.window_secs * 2
        stale = [k for k, w in self._windows.items() if not w or w[-1] < stale_cutoff]
        for k in stale:
            del self._windows[k]
        if stale:
            logger.debug(f"RateLimiter: evicted {len(stale)} stale keys")
        self._last_eviction = now
