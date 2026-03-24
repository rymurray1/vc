"""
Brave Search scraper.
Fallback search engine when DuckDuckGo is rate-limited.
Returns results in the same format as the DDG scraper.
"""

import time
import urllib.parse
import logging

import httpx
from bs4 import BeautifulSoup

from scraper.config import (
    CONNECT_TIMEOUT,
    READ_TIMEOUT,
    NUM_RESULTS,
    MAX_RETRIES,
    TOR_PROXY,
    get_random_headers,
    get_random_delay,
    get_backoff_delay,
)

logger = logging.getLogger(__name__)

BRAVE_SEARCH_URL = "https://search.brave.com/search"


class BraveScraper:
    """Scrapes Brave Search results. Same interface as GoogleScraper."""

    def __init__(self):
        self._last_request_time = 0
        self._request_count = 0
        self._block_count = 0

    def search(self, query, num_results=NUM_RESULTS):
        """Search Brave and return structured results matching Serper format."""
        self._enforce_rate_limit()

        params = {"q": query}
        url = f"{BRAVE_SEARCH_URL}?{urllib.parse.urlencode(params)}"

        for attempt in range(MAX_RETRIES):
            try:
                headers = get_random_headers()

                client_kwargs = {
                    "timeout": httpx.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT),
                    "follow_redirects": True,
                }
                if TOR_PROXY:
                    client_kwargs["proxy"] = TOR_PROXY

                with httpx.Client(**client_kwargs) as client:
                    response = client.get(url, headers=headers)

                self._last_request_time = time.time()
                self._request_count += 1

                if response.status_code == 429:
                    logger.warning(f"Brave rate limited on attempt {attempt + 1}")
                    self._handle_block(attempt)
                    continue

                if response.status_code != 200:
                    logger.warning(f"Brave HTTP {response.status_code} on attempt {attempt + 1}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(get_backoff_delay(attempt))
                    continue

                result = _parse_brave_html(response.text)

                if result and result.get("organic"):
                    result["organic"] = result["organic"][:num_results]

                self._block_count = 0
                organic_count = len(result.get("organic", []))
                logger.debug(f"Brave: {query[:50]}... -> {organic_count} results")
                return result

            except httpx.TimeoutException:
                logger.warning(f"Brave timeout on attempt {attempt + 1}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(get_backoff_delay(attempt))
            except Exception as e:
                logger.warning(f"Brave error on attempt {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(get_backoff_delay(attempt))

        logger.error(f"Brave: all {MAX_RETRIES} attempts failed for: {query[:50]}...")
        return None

    def close(self):
        pass

    def _enforce_rate_limit(self):
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            delay = get_random_delay()
            if elapsed < delay:
                time.sleep(delay - elapsed)

    def _handle_block(self, attempt):
        self._block_count += 1
        backoff = get_backoff_delay(attempt + self._block_count)
        logger.warning(f"Brave backing off {backoff:.1f}s")
        time.sleep(backoff)

    @property
    def stats(self):
        return {
            "total_requests": self._request_count,
            "blocks_encountered": self._block_count,
        }


def _parse_brave_html(html):
    """Parse Brave Search HTML into Serper-compatible format."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for snippet_div in soup.select("div.snippet"):
        # Link and title
        a = snippet_div.select_one("a.svelte-14r20fy") or snippet_div.select_one("a[href^='http']")
        if not a:
            continue

        link = a.get("href", "")
        if not link or "brave.com" in link:
            continue

        # Title
        title_el = snippet_div.select_one("div.search-snippet-title") or snippet_div.select_one("div.title")
        title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)

        # Snippet/description
        desc_el = snippet_div.select_one("div.generic-snippet div.content") or snippet_div.select_one("div.generic-snippet")
        snippet = desc_el.get_text(strip=True) if desc_el else ""

        if title and link:
            results.append({
                "title": title,
                "link": link,
                "snippet": snippet,
            })

    return {
        "organic": results,
        "knowledgeGraph": {},
    }
