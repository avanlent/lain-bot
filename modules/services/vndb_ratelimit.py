from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


class RateLimitError(RuntimeError):
    """Raised when the VNDB API hard limit is reached."""

    def __init__(self, retry_after: float) -> None:
        super().__init__("VNDB API hard rate limit reached")
        self.retry_after = retry_after


class SyncBudgetError(RuntimeError):
    """Raised when the reserved sync budget has been exhausted."""

    def __init__(self, retry_after: float) -> None:
        super().__init__("VNDB sync budget temporarily exhausted")
        self.retry_after = retry_after


@dataclass
class ConsumeResult:
    remaining: int
    retry_after: float


class VndbRateLimiter:
    """Fixed-window limiter to keep VNDB usage under ~200 requests / 5 minutes."""

    def __init__(self, *, max_requests: int = 200, sync_threshold: int = 195, window_seconds: int = 300) -> None:
        if sync_threshold > max_requests:
            raise ValueError("Sync threshold cannot exceed the maximum request budget")
        self._max_requests = max_requests
        self._sync_threshold = sync_threshold
        self._window_seconds = window_seconds

        self._lock = asyncio.Lock()
        now = time.monotonic()
        self._window_start: float = now
        self._reset_at: float = now + window_seconds
        self._count: int = 0

    async def consume(self, *, for_sync: bool) -> ConsumeResult:
        async with self._lock:
            now = time.monotonic()
            self._maybe_reset(now)

            if for_sync and self._count >= self._sync_threshold:
                retry_after = max(0.0, self._reset_at - now)
                raise SyncBudgetError(retry_after)

            self._count += 1
            remaining = max(0, self._max_requests - self._count)
            return ConsumeResult(
                remaining=remaining,
                retry_after=max(0.0, self._reset_at - now),
            )

    async def mark_limited(self, retry_after: float | None = None) -> float:
        """Force the limiter into a limited state after a 429 response."""
        async with self._lock:
            now = time.monotonic()
            self._maybe_reset(now)

            current_remaining = max(0.0, self._reset_at - now)
            cooldown = current_remaining
            if retry_after is not None:
                cooldown = max(cooldown, max(0.0, retry_after))

            self._count = self._max_requests
            self._reset_at = now + cooldown
            self._window_start = self._reset_at - self._window_seconds

            return max(0.0, self._reset_at - now)

    def _maybe_reset(self, now: float) -> None:
        if now >= self._reset_at:
            self._window_start = now
            self._reset_at = now + self._window_seconds
            self._count = 0


def parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

