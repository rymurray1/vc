"""
VC firm website URL discovery.
Uses the internal search scraper to find official websites
for VC firms that don't have URLs in vc_tags.json.
"""

import json
import re
import time
import logging
from pathlib import Path
from urllib.parse import urlparse

from scraper import MultiScraper

logger = logging.getLogger(__name__)

DEFAULT_VC_TAGS_PATH = Path(__file__).parent.parent / "vc-main" / "vc_tags.json"

# Domains that are never the VC's own website
SKIP_DOMAINS = {
    "linkedin.com", "www.linkedin.com",
    "twitter.com", "x.com",
    "facebook.com", "www.facebook.com",
    "instagram.com", "www.instagram.com",
    "youtube.com", "www.youtube.com",
    "crunchbase.com", "www.crunchbase.com",
    "pitchbook.com", "www.pitchbook.com",
    "tracxn.com", "www.tracxn.com",
    "dealroom.co", "www.dealroom.co",
    "bloomberg.com", "www.bloomberg.com",
    "reuters.com", "www.reuters.com",
    "techcrunch.com",
    "wikipedia.org", "en.wikipedia.org",
    "forbes.com", "www.forbes.com",
    "businessinsider.com", "www.businessinsider.com",
    "medium.com",
    "duckduckgo.com",
    "bing.com", "www.bing.com",
    "google.com", "www.google.com",
    "cbinsights.com", "www.cbinsights.com",
    "wellfound.com", "angel.co",
    "glassdoor.com", "www.glassdoor.com",
    "reddit.com", "www.reddit.com",
    "amazon.com", "www.amazon.com",
    "sec.gov", "www.sec.gov",
    "yelp.com",
}

# Patterns that suggest a URL is the VC's official site
VC_SITE_PATTERNS = [
    r"\.vc$", r"\.vc/", r"ventures\.com", r"capital\.com",
    r"partners\.com", r"fund\.com", r"invest",
]


class URLDiscovery:
    """Discovers official website URLs for VC firms using search."""

    def __init__(self, vc_tags_path=None):
        self.vc_tags_path = Path(vc_tags_path) if vc_tags_path else DEFAULT_VC_TAGS_PATH
        self.scraper = MultiScraper()
        self.progress = {
            "status": "idle",
            "total": 0,
            "processed": 0,
            "found": 0,
            "not_found": 0,
            "current_firm": "",
        }

    def get_firms_without_urls(self):
        """Return list of firm names that have no website URL."""
        tags = self._load_tags()
        return [name for name, meta in tags.items() if not meta.get("website")]

    def discover_url(self, firm_name):
        """
        Search for a VC firm's official website URL.

        Returns:
            str: The discovered URL, or empty string if not found.
        """
        query = f'"{firm_name}" venture capital official website'
        result = self.scraper.search(query)

        if not result or not result.get("organic"):
            return ""

        # Score each result URL
        candidates = []
        for r in result["organic"][:8]:
            link = r.get("link", "")
            title = r.get("title", "")

            if not link or not link.startswith("http"):
                continue

            parsed = urlparse(link)
            domain = parsed.netloc.lower()

            # Skip known non-VC domains
            if domain in SKIP_DOMAINS:
                continue

            # Skip DDG ad redirect URLs
            if "duckduckgo.com" in link or "bing.com/aclick" in link:
                continue

            score = 0

            # Firm name appears in domain
            firm_slug = firm_name.lower().replace(" ", "").replace("-", "").replace(".", "")
            domain_slug = domain.replace("www.", "").replace("-", "").replace(".", "")
            if firm_slug in domain_slug or domain_slug in firm_slug:
                score += 20

            # Partial firm name match in domain
            firm_words = firm_name.lower().split()
            for word in firm_words:
                if len(word) > 3 and word in domain.lower():
                    score += 5

            # Domain looks like a VC site
            for pattern in VC_SITE_PATTERNS:
                if re.search(pattern, domain):
                    score += 3

            # Title contains the firm name
            if firm_name.lower() in title.lower():
                score += 10

            # Title mentions venture, capital, portfolio
            title_lower = title.lower()
            if any(kw in title_lower for kw in ["venture", "capital", "portfolio", "invest"]):
                score += 2

            # It's a homepage (short path)
            if parsed.path in ("", "/", "/en", "/en/"):
                score += 3

            if score > 0:
                # Normalize to just the base URL
                base_url = f"{parsed.scheme}://{parsed.netloc}/"
                candidates.append((score, base_url, domain, title))

        if not candidates:
            return ""

        # Return highest-scoring candidate
        candidates.sort(key=lambda x: -x[0])
        best_score, best_url, best_domain, best_title = candidates[0]

        logger.debug(f"{firm_name} -> {best_url} (score={best_score}, title={best_title[:50]})")
        return best_url

    def discover_batch(self, limit=None, dry_run=False, callback=None):
        """
        Discover URLs for all firms missing them.

        Args:
            limit: Max firms to process (None = all)
            dry_run: If True, don't save changes
            callback: Optional progress callback

        Returns:
            dict with discovery stats
        """
        tags = self._load_tags()
        missing = [(name, meta) for name, meta in tags.items() if not meta.get("website")]

        if limit:
            missing = missing[:limit]

        self.progress = {
            "status": "running",
            "total": len(missing),
            "processed": 0,
            "found": 0,
            "not_found": 0,
            "current_firm": "",
            "results": [],
        }

        for i, (firm_name, meta) in enumerate(missing):
            self.progress["current_firm"] = firm_name
            self.progress["processed"] = i

            if callback:
                callback(self.progress)

            logger.info(f"[{i+1}/{len(missing)}] Discovering URL: {firm_name}")

            try:
                url = self.discover_url(firm_name)

                if url:
                    self.progress["found"] += 1
                    self.progress["results"].append({
                        "firm": firm_name,
                        "url": url,
                        "status": "found",
                    })
                    logger.info(f"  Found: {url}")

                    if not dry_run:
                        tags[firm_name]["website"] = url
                        self._save_tags(tags)
                else:
                    self.progress["not_found"] += 1
                    self.progress["results"].append({
                        "firm": firm_name,
                        "url": "",
                        "status": "not_found",
                    })
                    logger.info(f"  Not found")

            except Exception as e:
                self.progress["not_found"] += 1
                logger.error(f"  Error: {e}")

        self.progress["processed"] = len(missing)
        self.progress["status"] = "completed"
        self.progress["current_firm"] = ""

        if callback:
            callback(self.progress)

        return self.progress

    def _load_tags(self):
        """Load vc_tags.json."""
        with open(self.vc_tags_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_tags(self, data):
        """Save vc_tags.json."""
        with open(self.vc_tags_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
