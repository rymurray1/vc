"""
Search engine scraper using DuckDuckGo Lite.
Returns structured search results as a drop-in replacement for Serper.dev.

Uses DuckDuckGo Lite (lite.duckduckgo.com) which serves plain HTML —
no JavaScript rendering or headless browser needed.
"""

import time
import urllib.parse
import logging

import httpx

from scraper.config import (
    READ_TIMEOUT,
    CONNECT_TIMEOUT,
    NUM_RESULTS,
    MAX_RETRIES,
    get_random_headers,
    get_random_delay,
    get_backoff_delay,
)
from scraper.parser import parse_ddg_lite_html, is_blocked

logger = logging.getLogger(__name__)

DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"


class GoogleScraper:
    """
    Scrapes DuckDuckGo Lite search results and returns structured data
    matching the Serper.dev response format.

    Named GoogleScraper for backward compatibility with existing code
    that references this class.
    """

    def __init__(self):
        self._last_request_time = 0
        self._request_count = 0
        self._block_count = 0

    def search(self, query, num_results=NUM_RESULTS):
        """
        Search and return structured results.

        Args:
            query: Search query string
            num_results: Number of results to request (default 10)

        Returns:
            dict matching Serper format:
            {
                "organic": [{"title": str, "link": str, "snippet": str}, ...],
                "knowledgeGraph": {...}
            }
            Returns None on failure.
        """
        self._enforce_rate_limit()

        for attempt in range(MAX_RETRIES):
            try:
                headers = get_random_headers()

                with httpx.Client(
                    timeout=httpx.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT),
                    follow_redirects=True,
                ) as client:
                    response = client.post(
                        DDG_LITE_URL,
                        data={"q": query},
                        headers=headers,
                    )

                self._last_request_time = time.time()
                self._request_count += 1

                if response.status_code == 429:
                    logger.warning(f"Rate limited (429) on attempt {attempt + 1}")
                    self._handle_block(attempt)
                    continue

                if response.status_code not in (200, 202):
                    logger.warning(f"HTTP {response.status_code} on attempt {attempt + 1}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(get_backoff_delay(attempt))
                    continue

                html = response.text

                if is_blocked(html):
                    logger.warning(f"Blocked on attempt {attempt + 1}")
                    self._handle_block(attempt)
                    continue

                result = parse_ddg_lite_html(html)

                # If 202 with no results, DDG is rate-limiting; back off
                if response.status_code == 202 and not result.get("organic"):
                    wait = 5 + attempt * 3
                    logger.debug(f"DDG 202 with no results, backing off {wait}s...")
                    time.sleep(wait)
                    # Also reset the rate limit timer so next request gets full delay
                    self._last_request_time = time.time()
                    continue

                # Trim to requested number
                if result and "organic" in result:
                    result["organic"] = result["organic"][:num_results]

                # Reset block count on success
                self._block_count = 0

                organic_count = len(result.get("organic", []))
                logger.debug(f"Query: {query[:50]}... -> {organic_count} results")

                return result

            except httpx.TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1} for query: {query[:50]}...")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(get_backoff_delay(attempt))
            except httpx.HTTPError as e:
                logger.warning(f"HTTP error on attempt {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(get_backoff_delay(attempt))
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(get_backoff_delay(attempt))

        logger.error(f"All {MAX_RETRIES} attempts failed for query: {query[:50]}...")
        return None

    def close(self):
        """No-op for compatibility. No persistent resources to clean up."""
        pass

    def _enforce_rate_limit(self):
        """Wait if we're making requests too quickly."""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            delay = get_random_delay()
            if elapsed < delay:
                wait_time = delay - elapsed
                time.sleep(wait_time)

    def _handle_block(self, attempt):
        """Handle a block by backing off."""
        self._block_count += 1
        backoff = get_backoff_delay(attempt + self._block_count)
        logger.warning(f"Backing off for {backoff:.1f}s (block count: {self._block_count})")
        time.sleep(backoff)

    @property
    def stats(self):
        """Return scraper statistics."""
        return {
            "total_requests": self._request_count,
            "blocks_encountered": self._block_count,
        }
