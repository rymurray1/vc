"""
VC firm discovery scraper.
Searches for venture capital firms by sector, geography, and stage,
then adds them to vc_tags.json and firms.json for the rest of the pipeline.

This is Step 0 — it feeds new VCs into the system so Steps 1-4 can process them.
"""

import json
import re
import time
import logging
from pathlib import Path

from scraper import MultiScraper

logger = logging.getLogger(__name__)

DEFAULT_VC_TAGS_PATH = Path(__file__).parent.parent / "vc-main" / "vc_tags.json"
DEFAULT_FIRMS_PATH = Path(__file__).parent.parent / "vc-main" / "firms.json"

# Search queries to discover VCs across sectors and geographies
DISCOVERY_QUERIES = [
    # By sector
    'list of venture capital firms investing in AI startups',
    'top venture capital firms artificial intelligence machine learning',
    'venture capital firms biotech life sciences investments',
    'best VC firms healthcare healthtech investors',
    'venture capital firms fintech financial technology',
    'climate tech venture capital investors list',
    'clean energy venture capital firms',
    'SaaS enterprise software venture capital firms',
    'consumer tech venture capital investors',
    'industrials manufacturing venture capital firms',
    'crypto web3 blockchain venture capital',
    'real estate proptech venture capital firms',
    'food agriculture agtech venture capital',
    'cybersecurity venture capital investors',
    'deep tech frontier tech venture capital firms',
    'defense tech aerospace venture capital',
    'education edtech venture capital firms',
    'supply chain logistics venture capital',
    'space tech venture capital investors',
    'robotics automation venture capital firms',
    # By stage
    'top seed stage venture capital firms',
    'pre-seed venture capital investors list',
    'series A venture capital firms',
    'growth stage venture capital firms',
    'late stage crossover venture capital',
    # By geography
    'top venture capital firms silicon valley',
    'venture capital firms new york city',
    'boston venture capital firms list',
    'venture capital firms austin texas',
    'venture capital firms los angeles',
    'venture capital firms chicago',
    'venture capital firms seattle',
    'venture capital firms miami',
    'european venture capital firms list',
    'london venture capital firms',
    'berlin venture capital firms',
    'venture capital firms israel',
    'venture capital firms india',
    'southeast asia venture capital firms',
    'canadian venture capital firms',
    'latin america venture capital firms',
    # By lists / rankings
    'top 100 venture capital firms 2024',
    'top 100 venture capital firms 2025',
    'best venture capital firms Forbes Midas list',
    'most active venture capital firms 2025',
    'emerging venture capital firms to watch',
    'new venture capital firms launched 2024 2025',
    'top micro VC firms list',
    'top solo GP venture capital firms',
    'corporate venture capital firms list',
    'university venture capital funds',
]

# Words that indicate a result is a VC firm name (not an article title)
VC_INDICATORS = [
    "ventures", "capital", "partners", "vc", "fund", "invest",
    "equity", "group", "management", "advisors",
]

# Known non-VC names to skip
SKIP_NAMES = {
    "venture capital", "top venture", "best venture", "list of",
    "forbes", "techcrunch", "crunchbase", "pitchbook",
    "wikipedia", "investopedia", "bloomberg", "reuters",
    "the information", "the verge", "wired", "axios",
    "read more", "learn more", "see all", "view all",
    "united states", "silicon valley", "new york",
}


class VCDiscovery:
    """Discovers new VC firms and adds them to the database."""

    def __init__(self, vc_tags_path=None, firms_path=None):
        self.vc_tags_path = Path(vc_tags_path) if vc_tags_path else DEFAULT_VC_TAGS_PATH
        self.firms_path = Path(firms_path) if firms_path else DEFAULT_FIRMS_PATH
        self.scraper = MultiScraper()
        self.progress = {
            "status": "idle",
            "total_queries": 0,
            "queries_completed": 0,
            "new_vcs_found": 0,
            "already_known": 0,
            "current_query": "",
        }

    def get_existing_firms(self):
        """Return set of firm names already in the database."""
        tags = self._load_tags()
        return set(tags.keys())

    def discover(self, queries=None, limit=None, dry_run=False, callback=None):
        """
        Run discovery queries and add new VCs to the database.

        Args:
            queries: List of search queries (default: DISCOVERY_QUERIES)
            limit: Max queries to run (default: all)
            dry_run: If True, don't save
            callback: Progress callback

        Returns:
            dict with stats and list of new VCs found
        """
        if queries is None:
            queries = DISCOVERY_QUERIES

        if limit:
            queries = queries[:limit]

        existing = self.get_existing_firms()
        existing_lower = {name.lower() for name in existing}
        tags = self._load_tags()
        firms = self._load_firms()
        firm_names_in_firms = {f["name"] for f in firms}

        self.progress = {
            "status": "running",
            "total_queries": len(queries),
            "queries_completed": 0,
            "new_vcs_found": 0,
            "already_known": 0,
            "current_query": "",
            "new_firms": [],
        }

        for i, query in enumerate(queries):
            self.progress["current_query"] = query
            self.progress["queries_completed"] = i

            if callback:
                callback(self.progress)

            logger.info(f"[{i+1}/{len(queries)}] {query[:60]}...")

            result = self.scraper.search(query)
            if not result or not result.get("organic"):
                continue

            for r in result["organic"][:8]:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                link = r.get("link", "")

                if "duckduckgo.com" in link or "bing.com" in link:
                    continue

                # Extract VC firm names from titles and snippets
                names = self._extract_vc_names(f"{title} {snippet}")

                for name in names:
                    if name.lower() in existing_lower:
                        self.progress["already_known"] += 1
                        continue

                    # New VC found
                    existing_lower.add(name.lower())
                    self.progress["new_vcs_found"] += 1
                    self.progress["new_firms"].append(name)

                    logger.info(f"  NEW: {name}")

                    if not dry_run:
                        # Add to vc_tags.json
                        tags[name] = {
                            "focus": [],
                            "ma_presence": False,
                            "hq": "",
                            "website": "",
                        }

                        # Add to firms.json
                        if name not in firm_names_in_firms:
                            firms.append({
                                "name": name,
                                "country": "United States",
                                "investments": [],
                            })
                            firm_names_in_firms.add(name)

            # Save after each query batch
            if not dry_run and self.progress["new_vcs_found"] > 0:
                self._save_tags(tags)
                self._save_firms(firms)

            time.sleep(0.3)

        self.progress["queries_completed"] = len(queries)
        self.progress["status"] = "completed"
        self.progress["current_query"] = ""

        if callback:
            callback(self.progress)

        return self.progress

    def _extract_vc_names(self, text):
        """
        Extract VC firm names from search result text.
        Looks for patterns like "Firm Name Capital", "Firm Ventures", etc.
        """
        names = []

        # Pattern 1: "Name + VC indicator word"
        # e.g. "Sequoia Capital", "Andreessen Horowitz", "Lux Capital"
        patterns = [
            r'\b([A-Z][A-Za-z\']+(?:\s+[A-Z][A-Za-z\']+){0,3}\s+(?:Ventures|Capital|Partners|VC|Fund|Equity|Group|Management|Advisors|Investment|Investments))\b',
            r'\b([A-Z][A-Za-z\']+(?:\s+[A-Z][A-Za-z\']+){0,2}\s+Venture\s+Partners)\b',
            r'\b([A-Z][A-Za-z\']+(?:\s+[A-Z][A-Za-z\']+){0,2}\s+Venture\s+Capital)\b',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                clean = match.strip()
                if self._is_valid_vc_name(clean):
                    names.append(clean)

        # Pattern 2: Known VC name formats without indicator words
        # e.g. "a16z", "Y Combinator", "8VC"
        # These are harder to catch generically, but the indicator-word
        # pattern covers the vast majority

        return list(set(names))

    def _is_valid_vc_name(self, name):
        """Validate that a string looks like a VC firm name."""
        if not name or len(name) < 3 or len(name) > 50:
            return False

        lower = name.lower()

        # Skip known non-VC strings
        if any(skip in lower for skip in SKIP_NAMES):
            return False

        # Should have 2-6 words
        words = name.split()
        if len(words) < 1 or len(words) > 6:
            return False

        # Should end with a VC indicator word (already enforced by regex,
        # but double-check)
        last_word = words[-1].lower()
        if last_word not in ["ventures", "capital", "partners", "vc", "fund",
                             "equity", "group", "management", "advisors",
                             "investment", "investments"]:
            return False

        # Skip if it's a generic phrase
        generic = {
            "venture capital", "venture capital firms", "venture capital fund",
            "corporate venture capital", "top venture capital",
            "best venture capital", "venture capital investors",
        }
        if lower in generic:
            return False

        # First word should not be a generic adjective/article
        generic_first_words = {
            "top", "best", "most", "new", "leading", "major", "biggest",
            "largest", "active", "notable", "prominent", "emerging",
            "other", "more", "some", "many", "several", "various",
            "global", "local", "regional", "national", "international",
            "early", "late", "seed", "growth", "stage",
            "the", "a", "an", "this", "that", "these", "those",
        }
        if words[0].lower() in generic_first_words:
            return False

        # Must have at least 2 words (firm name + indicator)
        if len(words) < 2:
            return False

        return True

    def _load_tags(self):
        with open(self.vc_tags_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_tags(self, data):
        with open(self.vc_tags_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_firms(self):
        with open(self.firms_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_firms(self, data):
        with open(self.firms_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
