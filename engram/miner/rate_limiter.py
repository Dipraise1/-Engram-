"""
Engram Miner — Per-hotkey Rate Limiter

Limits ingest requests per hotkey using a sliding window (token bucket).
Configured via env vars:
  RATE_LIMIT_MAX_REQUESTS  — max ingest requests per window (default 100)
  RATE_LIMIT_WINDOW_SECS   — window duration in seconds (default 60)
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from loguru import logger

MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))
WINDOW_SECS  = int(os.getenv("RATE_LIMIT_WINDOW_SECS", "60"))


class RateLimiter:
    """
    Sliding window rate limiter keyed by hotkey.

    Tracks the timestamps of recent requests in a deque per hotkey.
    A request is allowed if fewer than MAX_REQUESTS were made in the
    last WINDOW_SECS seconds.
    """

    def __init__(
        self,
        max_requests: int = MAX_REQUESTS,
        window_secs: int = WINDOW_SECS,
    ) -> None:
        self.max_requests = max_requests
        self.window_secs  = window_secs
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, hotkey: str) -> bool:
        """Return True if the hotkey is within its rate limit."""
        now = time.time()
        window = self._windows[hotkey]

        # Evict timestamps outside the sliding window
        cutoff = now - self.window_secs
        while window and window[0] < cutoff:
            window.popleft()

        if len(window) >= self.max_requests:
            logger.warning(
                f"Rate limit exceeded | hotkey={hotkey[:16]}… | "
                f"{len(window)}/{self.max_requests} req in {self.window_secs}s"
            )
            return False

        window.append(now)
        return True

    def check(self, hotkey: str) -> None:
        """Raise ValueError if the hotkey is rate-limited."""
        if not self.is_allowed(hotkey):
            raise ValueError(
                f"Rate limit exceeded: max {self.max_requests} ingest requests "
                f"per {self.window_secs}s per hotkey"
            )

    def stats(self, hotkey: str) -> dict:
        """Return current usage stats for a hotkey."""
        now = time.time()
        window = self._windows.get(hotkey, deque())
        cutoff = now - self.window_secs
        recent = sum(1 for t in window if t >= cutoff)
        return {
            "hotkey": hotkey,
            "requests_in_window": recent,
            "max_requests": self.max_requests,
            "window_secs": self.window_secs,
            "remaining": max(0, self.max_requests - recent),
        }

    def reset(self, hotkey: str) -> None:
        """Clear rate limit state for a hotkey (admin use)."""
        self._windows.pop(hotkey, None)
