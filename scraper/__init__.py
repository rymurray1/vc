"""
Internal search scraper — drop-in replacement for Serper.dev.
Uses DuckDuckGo as primary, Brave Search as fallback.

Usage:
    from scraper import search

    results = search("OpenAI founder CEO")
    for r in results.get("organic", []):
        print(r["title"], r["link"])
"""

import logging

from scraper.google import GoogleScraper
from scraper.brave import BraveScraper

logger = logging.getLogger(__name__)

# Module-level scraper instances
_ddg = GoogleScraper()
_brave = BraveScraper()


def search(query, num=10):
    """
    Search and return structured results. Tries DuckDuckGo first,
    falls back to Brave Search if DDG fails or is rate-limited.

    Returns:
        dict with "organic" and "knowledgeGraph" keys, or None.
    """
    # Try DuckDuckGo first
    result = _ddg.search(query, num_results=num)
    if result and result.get("organic"):
        return result

    # Fallback to Brave
    logger.info(f"DDG failed, trying Brave for: {query[:50]}...")
    result = _brave.search(query, num_results=num)
    if result and result.get("organic"):
        return result

    return None


def get_scraper():
    """Get a fresh multi-engine scraper instance for batch operations."""
    return MultiScraper()


class MultiScraper:
    """Scraper that tries DDG then Brave. Same interface as GoogleScraper."""

    def __init__(self):
        self._ddg = GoogleScraper()
        self._brave = BraveScraper()

    def search(self, query, num_results=10):
        result = self._ddg.search(query, num_results=num_results)
        if result and result.get("organic"):
            return result

        logger.info(f"DDG failed, trying Brave for: {query[:50]}...")
        return self._brave.search(query, num_results=num_results)

    def close(self):
        self._ddg.close()
        self._brave.close()

    @property
    def stats(self):
        return {
            "ddg": self._ddg.stats,
            "brave": self._brave.stats,
        }
