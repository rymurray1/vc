"""
Portfolio company discovery for VC firms.
Finds companies that a VC has invested in using two strategies:
  1. Search-based: DDG search for "backed by {firm}" to find portfolio companies
  2. Direct scrape: Try the VC's /portfolio page for company links

Output matches firms.json format: [{"company": str, "url": str}, ...]
"""

import json
import re
import time
import logging
from pathlib import Path
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup

from scraper import MultiScraper
from scraper.config import get_random_headers

logger = logging.getLogger(__name__)

DEFAULT_FIRMS_PATH = Path(__file__).parent.parent / "vc-main" / "firms.json"
DEFAULT_VC_TAGS_PATH = Path(__file__).parent.parent / "vc-main" / "vc_tags.json"
DEFAULT_FOUNDERS_PATH = Path(__file__).parent.parent / "vc-main" / "founders.json"

# Common portfolio page paths to try on VC websites
PORTFOLIO_PATHS = [
    "/portfolio", "/portfolio/", "/companies", "/companies/",
    "/investments", "/our-portfolio", "/startups",
]

# Domains that are never portfolio companies
SKIP_DOMAINS = {
    "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "youtube.com", "medium.com", "github.com",
    "google.com", "apple.com", "amazonaws.com", "cloudfront.net",
    "crunchbase.com", "pitchbook.com", "tracxn.com",
    "duckduckgo.com", "bing.com", "wikipedia.org",
    "fonts.googleapis.com", "gstatic.com",
    "hubspot.com", "mailchimp.com", "squarespace.com",
    "wixsite.com", "wordpress.com", "wp.com",
}

# Navigation link text to skip
SKIP_LINK_TEXT = {
    "about", "team", "contact", "blog", "news", "press", "careers",
    "privacy", "terms", "login", "signup", "home", "resources",
    "events", "podcast", "newsletter", "subscribe", "apply",
    "cookie", "legal", "sitemap", "back", "next", "previous",
    "visit website", "learn more", "read more", "see all",
    "view more", "load more", "show more", "view all",
    "portfolio", "companies", "investments", "about us",
}


class PortfolioScraper:
    """Discovers portfolio companies for VC firms."""

    def __init__(self, firms_path=None, vc_tags_path=None, founders_path=None):
        self.firms_path = Path(firms_path) if firms_path else DEFAULT_FIRMS_PATH
        self.vc_tags_path = Path(vc_tags_path) if vc_tags_path else DEFAULT_VC_TAGS_PATH
        self.founders_path = Path(founders_path) if founders_path else DEFAULT_FOUNDERS_PATH
        self.scraper = MultiScraper()
        self.progress = {
            "status": "idle",
            "total": 0,
            "processed": 0,
            "found": 0,
            "skipped": 0,
            "current_firm": "",
        }

    def get_empty_firms(self):
        """Return firm names with 0 investments."""
        firms = self._load_firms()
        return [f["name"] for f in firms if len(f.get("investments", [])) == 0]

    def discover_portfolio(self, firm_name, website_url=None):
        """
        Discover portfolio companies for a single VC firm.
        Returns list of {"company": str, "url": str} dicts.
        """
        all_companies = {}

        # Strategy 1: Search for companies backed by this firm
        search_results = self._search_backed_companies(firm_name)
        all_companies.update(search_results)

        # Strategy 2: Scrape the VC's portfolio page
        if website_url:
            scraped = self._scrape_portfolio_page(firm_name, website_url)
            for name, url in scraped.items():
                if name not in all_companies or (url and not all_companies[name]):
                    all_companies[name] = url

        # Convert to list
        investments = []
        for company, url in sorted(all_companies.items()):
            investments.append({"company": company, "url": url})

        return investments

    def discover_batch(self, limit=None, dry_run=False, callback=None):
        """Discover portfolios for all empty firms."""
        firms = self._load_firms()
        tags = self._load_tags()
        empty = [f for f in firms if len(f.get("investments", [])) == 0]

        if limit:
            empty = empty[:limit]

        self.progress = {
            "status": "running",
            "total": len(empty),
            "processed": 0,
            "found": 0,
            "skipped": 0,
            "current_firm": "",
            "results": [],
        }

        for i, firm in enumerate(empty):
            firm_name = firm["name"]
            self.progress["current_firm"] = firm_name
            self.progress["processed"] = i

            if callback:
                callback(self.progress)

            website_url = tags.get(firm_name, {}).get("website", "")
            logger.info(f"[{i+1}/{len(empty)}] {firm_name}")

            try:
                investments = self.discover_portfolio(firm_name, website_url)

                if investments:
                    self.progress["found"] += 1
                    self.progress["results"].append({
                        "firm": firm_name,
                        "count": len(investments),
                        "sample": [c["company"] for c in investments[:5]],
                    })
                    logger.info(f"  Found {len(investments)} companies")

                    if not dry_run:
                        self._update_firm(firms, firm_name, investments)
                        self._save_firms(firms)
                        self._add_to_founders(investments)
                else:
                    self.progress["skipped"] += 1
                    logger.info(f"  No companies found")

            except Exception as e:
                self.progress["skipped"] += 1
                logger.error(f"  Error: {e}")

        self.progress["processed"] = len(empty)
        self.progress["status"] = "completed"
        self.progress["current_firm"] = ""

        if callback:
            callback(self.progress)

        return self.progress

    # ── Search-based discovery ──────────────────────────────────────

    def _search_backed_companies(self, firm_name):
        """
        Search DDG for companies backed/funded by this VC.
        Extracts company names from article titles and snippets.
        """
        companies = {}

        queries = [
            f'"backed by {firm_name}"',
            f'"{firm_name}" portfolio company',
        ]

        for query in queries:
            result = self.scraper.search(query)
            if not result or not result.get("organic"):
                continue

            for r in result["organic"][:8]:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                link = r.get("link", "")

                if "duckduckgo.com" in link or "bing.com" in link:
                    continue

                # Extract company from article title
                name = self._company_from_title(title, firm_name)
                if name:
                    companies[name] = ""

                # Extract from "backed by" patterns in snippet
                for found in self._companies_from_backed_pattern(
                    f"{title} {snippet}", firm_name
                ):
                    if found not in companies:
                        companies[found] = ""

            time.sleep(0.5)

        return companies

    def _company_from_title(self, title, firm_name):
        """
        Extract company name from a search result title.
        e.g. "Sortera raises $73M backed by BEV - Observer" -> "Sortera"
        """
        if not title or firm_name.lower() in title.lower()[:len(firm_name)+5]:
            return None

        # Split title on delimiters, take the first part
        parts = re.split(r'\s*[-–—|:]\s*', title)
        if not parts:
            return None

        candidate = parts[0].strip()

        # Remove trailing action words
        candidate = re.sub(
            r'\s+(raises?|secures?|closes?|gets?|nabs?|announces?|'
            r'launches?|plans?|lands?|receives?|wins?|is\b).*',
            '', candidate, flags=re.IGNORECASE
        ).strip()

        # Remove leading articles
        candidate = re.sub(r'^(This |A |An |The )', '', candidate).strip()

        return self._validate_company(candidate, firm_name)

    def _companies_from_backed_pattern(self, text, firm_name):
        """Extract company names from 'X backed by FirmName' patterns."""
        results = []
        escaped = re.escape(firm_name)

        patterns = [
            rf'(\b[A-Z][A-Za-z0-9]{{1,25}})\s*(?:,\s*(?:a|an)\s+\w+\s*,?\s*)?(?:is\s+)?(?:also\s+)?backed by\s+{escaped}',
            rf'(\b[A-Z][A-Za-z0-9]{{1,25}})\s*(?:is\s+)?(?:also\s+)?funded by\s+{escaped}',
        ]

        for pattern in patterns:
            for match in re.findall(pattern, text):
                name = self._validate_company(match.strip(), firm_name)
                if name:
                    results.append(name)

        return results

    # ── Direct portfolio page scraping ──────────────────────────────

    def _scrape_portfolio_page(self, firm_name, base_url):
        """Try to scrape the VC's portfolio page for company links."""
        if not base_url.endswith("/"):
            base_url += "/"

        for path in PORTFOLIO_PATHS:
            url = urljoin(base_url, path)
            companies = self._scrape_page_for_companies(url, base_url)
            if len(companies) >= 3:  # Need at least 3 to be meaningful
                return companies

        return {}

    def _scrape_page_for_companies(self, url, base_url):
        """Scrape a page for external company links."""
        companies = {}
        headers = get_random_headers()

        try:
            with httpx.Client(timeout=12, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)

            if resp.status_code != 200:
                return companies

            soup = BeautifulSoup(resp.text, "html.parser")
            base_domain = urlparse(base_url).netloc.lower().replace("www.", "")

            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                text = a.get_text(strip=True)

                if not text or len(text) < 2 or len(text) > 40:
                    continue

                # Resolve relative URLs
                if href.startswith("/"):
                    href = urljoin(url, href)
                if not href.startswith("http"):
                    continue

                link_domain = urlparse(href).netloc.lower().replace("www.", "")

                # Must be external (not the VC's own site)
                if base_domain in link_domain or link_domain in base_domain:
                    continue

                # Skip known non-company domains
                if any(skip in link_domain for skip in SKIP_DOMAINS):
                    continue

                # Skip navigation text
                if text.lower().strip() in SKIP_LINK_TEXT:
                    continue

                name = self._validate_company(text.strip(), "")
                if name:
                    companies[name] = href

        except Exception as e:
            logger.debug(f"Error scraping {url}: {e}")

        return companies

    # ── Validation & helpers ────────────────────────────────────────

    def _validate_company(self, name, firm_name):
        """Return the name if it's a valid company, else None."""
        if not name or len(name) < 2 or len(name) > 40:
            return None

        # Must have alpha chars
        if sum(c.isalpha() for c in name) < 2:
            return None

        # Max 4 words
        if len(name.split()) > 4:
            return None

        lower = name.lower()

        # Not the firm itself
        if firm_name and (lower == firm_name.lower() or firm_name.lower() in lower):
            return None

        # Not a generic word
        skip = {
            "portfolio", "companies", "company", "investments", "fund",
            "venture", "capital", "partners", "about", "team", "contact",
            "blog", "news", "press", "home", "access", "discover",
            "connect", "explore", "overview", "search", "list",
            "privacy", "terms", "careers", "login", "signup",
            "consumer", "enterprise", "software", "united states",
            "new york", "san francisco", "cambridge", "boston",
            "early stage", "seed", "series", "growth", "billion",
            "deep tech", "green tech", "clean energy", "venture capital",
            "crunchbase", "pitchbook", "tracxn", "linkedin",
            "origination", "internship", "manager", "fellowship",
            "best startups", "high tech",
        }
        if lower in skip:
            return None

        # Reject sentence fragments
        bad_words = {
            "the", "and", "for", "with", "from", "that", "this",
            "also", "been", "were", "have", "has", "are", "was",
            "will", "our", "their", "your", "its", "more",
        }
        if any(w.lower() in bad_words for w in name.split()):
            return None

        # Reject if it contains sentence patterns
        if any(p in lower for p in [
            "backed by", "funded by", "invested", "raises", "raised",
            "provides", "includes", "based in", "founded in",
            "site:", "http", ".com/", "portfolio",
        ]):
            return None

        return name

    def _update_firm(self, firms, firm_name, investments):
        """Update a firm's investments in the firms list."""
        for firm in firms:
            if firm["name"] == firm_name:
                firm["investments"] = investments
                return

    def _add_to_founders(self, investments):
        """Add new companies to founders.json."""
        try:
            with open(self.founders_path, "r", encoding="utf-8") as f:
                founders = json.load(f)
        except FileNotFoundError:
            founders = {}

        added = 0
        for inv in investments:
            company = inv["company"]
            if company not in founders:
                founders[company] = {
                    "url": inv.get("url", ""),
                    "founders": [],
                    "ceo": {},
                }
                added += 1

        if added > 0:
            with open(self.founders_path, "w", encoding="utf-8") as f:
                json.dump(founders, f, indent=2, ensure_ascii=False)
            logger.info(f"  Added {added} new companies to founders.json")

    def _load_firms(self):
        with open(self.firms_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_firms(self, data):
        with open(self.firms_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_tags(self):
        with open(self.vc_tags_path, "r", encoding="utf-8") as f:
            return json.load(f)
