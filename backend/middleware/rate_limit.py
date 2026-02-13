"""
In-memory rate limiting for magic link operations.

For Phase 0, we use a simple in-memory dict.
For production scale, consider Redis or similar.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta


class RateLimiter:
    """
    Simple in-memory rate limiter.

    Tracks request counts per key (email or IP) within time windows.
    """

    def __init__(self):
        # key -> list of (timestamp, count) tuples
        self._requests: dict[str, list[tuple[datetime, int]]] = defaultdict(list)

    def check_rate_limit(self, key: str, max_requests: int, window_minutes: int = 60) -> bool:
        """
        Check if a key has exceeded the rate limit.

        Args:
            key: Identifier to rate limit (email or IP address)
            max_requests: Maximum requests allowed in the window
            window_minutes: Time window in minutes (default 60)

        Returns:
            True if under the limit, False if limit exceeded
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=window_minutes)

        # Clean up old entries
        self._requests[key] = [(ts, count) for ts, count in self._requests[key] if ts > cutoff]

        # Count recent requests
        total = sum(count for _, count in self._requests[key])

        if total >= max_requests:
            return False

        # Record this request
        self._requests[key].append((now, 1))
        return True

    def cleanup_old_entries(self, max_age_hours: int = 2):
        """
        Clean up rate limit entries older than specified hours.

        Args:
            max_age_hours: Remove entries older than this many hours
        """
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        for key in list(self._requests.keys()):
            self._requests[key] = [(ts, count) for ts, count in self._requests[key] if ts > cutoff]
            if not self._requests[key]:
                del self._requests[key]


# Global rate limiter instance
rate_limiter = RateLimiter()
