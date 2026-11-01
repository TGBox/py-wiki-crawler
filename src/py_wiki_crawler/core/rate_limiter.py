"""
Rate limiter and polite HTTP requester with exponential backoff.
"""

import logging
import time
from collections.abc import Callable

import requests

logger = logging.getLogger("py_wiki_crawler.rate_limiter")


class RateLimiter:
    """Controls request pacing and handles automatic retry with exponential backoff."""

    def __init__(
        self,
        base_delay: float = 0.4,
        max_retries: int = 4,
        initial_backoff: float = 1.0,
        backoff_factor: float = 2.0,
    ):
        self.base_delay = base_delay
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.backoff_factor = backoff_factor
        self.last_request_time: float = 0.0

    def wait(self) -> None:
        """Enforces polite pacing between regular requests."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.base_delay:
            time.sleep(self.base_delay - elapsed)
        self.last_request_time = time.time()

    def execute_with_retry(
        self, request_func: Callable[[], requests.Response], description: str = "HTTP request"
    ) -> requests.Response:
        """
        Executes an HTTP request function with retry logic and exponential backoff
        for rate limiting (429) or transient server errors (500, 502, 503, 504).
        """
        backoff = self.initial_backoff
        for attempt in range(1, self.max_retries + 1):
            self.wait()
            try:
                response = request_func()
                # Status 429 Too Many Requests or 5xx Server Error
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = response.headers.get("Retry-After")
                    sleep_time = (
                        float(retry_after) if retry_after and retry_after.isdigit() else backoff
                    )
                    logger.warning(
                        f"Server signalierte {response.status_code} ({description}). "
                        f"Warte {sleep_time:.1f}s vor Versuch {attempt + 1}/{self.max_retries}..."
                    )
                    time.sleep(sleep_time)
                    backoff *= self.backoff_factor
                    continue
                return response
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == self.max_retries:
                    raise
                logger.warning(
                    f"Netzwerkfehler bei {description}: {e}. "
                    f"Warte {backoff:.1f}s vor Versuch {attempt + 1}/{self.max_retries}..."
                )
                time.sleep(backoff)
                backoff *= self.backoff_factor

        # Final try
        self.wait()
        return request_func()
