# src/helpers/rate_limiter.py
from typing import Dict, Any
import time
from datetime import datetime
import logging
from dataclasses import dataclass
from threading import Lock

@dataclass
class RateLimit:
    count: int
    window_start: float
    lock: Lock

class RateLimiter:
    """Rate limiter for API endpoints."""

    def __init__(self, 
                 requests_per_second: int = 10,
                 window_size: int = 1):
        self._requests_per_second = requests_per_second
        self._window_size = window_size
        self._limits: Dict[str, RateLimit] = {}
        self._logger = logging.getLogger(__name__)

    def check_rate_limit(self, key: str) -> None:
        """
        Check if request should be rate limited.
        
        Args:
            key: Identifier for the rate limit (e.g., IP address)
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        current_time = time.time()

        if key not in self._limits:
            self._limits[key] = RateLimit(0, current_time, Lock())

        with self._limits[key].lock:
            limit = self._limits[key]
            
            # Check if window has expired
            if current_time - limit.window_start >= self._window_size:
                # Reset window
                limit.count = 0
                limit.window_start = current_time

            # Check limit
            if limit.count >= self._requests_per_second:
                self._logger.warning(f"Rate limit exceeded for {key}")
                raise RateLimitExceeded(
                    f"Rate limit of {self._requests_per_second} requests per {self._window_size} second(s) exceeded"
                )

            # Increment counter
            limit.count += 1
            self._logger.debug(f"Request count for {key}: {limit.count}")

    def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        if key in self._limits:
            del self._limits[key]

class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass