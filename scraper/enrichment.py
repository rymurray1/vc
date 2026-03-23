"""
Founder/CEO enrichment engine.
Uses the internal Google scraper to find founder names and LinkedIn profiles
for VC-backed companies. Replaces the old Serper.dev-based scripts.
"""

import json
import re
import time
import logging
from pathlib import Path

from scraper import MultiScraper
from scraper.config import MULTI_QUERY_DELAY

logger = logging.getLogger(__name__)

# Default path to founders.json (relative to repo root)
DEFAULT_FOUNDERS_PATH = Path(__file__).parent.parent / "founders.json"
DEFAULT_FIRMS_PATH = Path(__file__).parent.parent / "firms.json"


class EnrichmentEngine:
    """
    Multi-strategy founder enrichment using the internal Google scraper.
    Finds founder/CEO names and LinkedIn profiles for companies.
    """

    def __init__(self, founders_path=None, firms_path=None):
        self.founders_path = Path(founders_path) if founders_path else DEFAULT_FOUNDERS_PATH
        self.firms_path = Path(firms_path) if firms_path else DEFAULT_FIRMS_PATH
        self.scraper = MultiScraper()

        # Progress tracking
        self.progress = {
            "status": "idle",      # idle, running, completed, error
            "total": 0,
            "processed": 0,
            "enriched": 0,
            "failed": 0,
            "current_company": "",
            "errors": [],
        }

    def get_coverage_stats(self):
        """Return enrichment coverage statistics."""
        founders_data = self._load_founders()
        total = len(founders_data)
        enriched = sum(1 for v in founders_data.values() if v.get("founders"))
        empty = total - enriched

        return {
            "total_companies": total,
            "enriched": enriched,
            "empty": empty,
            "coverage_pct": round((enriched / total * 100), 1) if total > 0 else 0,
        }

    def get_incomplete_companies(self):
        """Return list of company names with empty founders."""
        founders_data = self._load_founders()
        return [k for k, v in founders_data.items() if not v.get("founders")]

    def enrich_company(self, company_name, company_url=None):
        """
        Enrich a single company with founder/CEO data using multi-strategy search.

        Returns:
            dict with "founders" and "ceo" keys, or None if nothing found.
        """
        queries = self._build_queries(company_name, company_url)

        all_names = set()
        all_linkedin = {}
        all_roles = {}  # name -> role (founder/ceo)

        for query in queries:
            result = self.scraper.search(query)
            if not result:
                continue

            names, linkedin_urls, roles = self._parse_search_results(company_name, result)
            all_names.update(names)
            all_linkedin.update(linkedin_urls)
            for name, role in roles.items():
                if name not in all_roles or role == "ceo":
                    all_roles[name] = role

            # Short delay between multi-strategy queries
            if MULTI_QUERY_DELAY > 0:
                time.sleep(MULTI_QUERY_DELAY)

        # Also check knowledge graph from last result
        if result and result.get("knowledgeGraph"):
            kg_names, kg_roles = self._parse_knowledge_graph(result["knowledgeGraph"])
            all_names.update(kg_names)
            all_roles.update(kg_roles)

        if not all_names:
            return None

        # Build founders list, prioritizing those with LinkedIn URLs and roles
        founders = []
        ceo = {}
        seen_names = set()

        # Sort: names with LinkedIn URLs first, then by role (ceo > founder)
        scored_names = []
        for name in all_names:
            if name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            linkedin_url = self._match_linkedin(name, all_linkedin)
            role = all_roles.get(name, "")
            score = 0
            if linkedin_url:
                score += 10
            if role == "ceo":
                score += 5
            elif role == "founder":
                score += 3
            scored_names.append((score, name, linkedin_url, role))

        scored_names.sort(key=lambda x: (-x[0], x[1]))

        for score, name, linkedin_url, role in scored_names[:8]:  # Cap at 8 founders
            founder_entry = {"name": name, "linkedin": linkedin_url}
            founders.append(founder_entry)

            if role == "ceo" and not ceo:
                ceo = founder_entry

        if not ceo and founders:
            ceo = founders[0]

        return {"founders": founders, "ceo": ceo}

    def enrich_batch(self, limit=None, dry_run=False, callback=None):
        """
        Enrich all companies with empty founders.

        Args:
            limit: Max number of companies to process (None = all)
            dry_run: If True, don't save changes
            callback: Optional function called with progress dict after each company

        Returns:
            dict with enrichment stats
        """
        founders_data = self._load_founders()
        incomplete = [(k, v) for k, v in founders_data.items() if not v.get("founders")]

        if limit:
            incomplete = incomplete[:limit]

        self.progress = {
            "status": "running",
            "total": len(incomplete),
            "processed": 0,
            "enriched": 0,
            "failed": 0,
            "current_company": "",
            "errors": [],
        }

        for i, (company_name, company_info) in enumerate(incomplete):
            self.progress["current_company"] = company_name
            self.progress["processed"] = i

            if callback:
                callback(self.progress)

            logger.info(f"[{i+1}/{len(incomplete)}] Enriching: {company_name}")

            try:
                company_url = company_info.get("url", "")
                result = self.enrich_company(company_name, company_url)

                if result and result["founders"]:
                    if not dry_run:
                        founders_data[company_name]["founders"] = result["founders"]
                        founders_data[company_name]["ceo"] = result["ceo"]
                        self._save_founders(founders_data)

                    self.progress["enriched"] += 1
                    names = ", ".join(f["name"] for f in result["founders"][:3])
                    logger.info(f"  Found: {names}")
                else:
                    self.progress["failed"] += 1
                    logger.info(f"  Not found")

            except Exception as e:
                self.progress["failed"] += 1
                self.progress["errors"].append(f"{company_name}: {str(e)}")
                logger.error(f"  Error: {e}")

        self.progress["processed"] = len(incomplete)
        self.progress["status"] = "completed"
        self.progress["current_company"] = ""

        if callback:
            callback(self.progress)

        return self.progress

    def _build_queries(self, company_name, company_url=None):
        """Build multi-strategy search queries for a company."""
        queries = [
            f"{company_name} founder CEO",
            f"{company_name} co-founder linkedin",
            f"{company_name} founders team",
        ]

        # If we have the company URL, use a site-targeted LinkedIn query
        if company_url:
            domain = company_url.replace("https://", "").replace("http://", "").split("/")[0]
            queries.append(
                f'site:linkedin.com/in "{company_name}" OR "{domain}" CEO OR founder'
            )
        else:
            queries.append(f'"{company_name}" founder linkedin site:linkedin.com/in')

        return queries

    def _parse_search_results(self, company_name, serper_data):
        """
        Extract founder names, LinkedIn URLs, and roles from search results.
        Returns (names_set, linkedin_dict, roles_dict).
        """
        names = set()
        linkedin_urls = {}  # slug -> full URL
        roles = {}  # name -> "founder" or "ceo"

        if not serper_data or "organic" not in serper_data:
            return names, linkedin_urls, roles

        for result in serper_data.get("organic", [])[:7]:
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")

            combined = f"{title} {snippet}"
            lower_combined = combined.lower()

            # Extract LinkedIn URLs
            found_urls = self._extract_linkedin_urls(f"{combined} {link}")
            for url in found_urls:
                slug = url.split("/in/")[-1].rstrip("/").lower()
                linkedin_urls[slug] = url

            # Extract names from LinkedIn-style titles
            # e.g. "John Doe - Founder at Company | LinkedIn"
            if "linkedin.com" in link:
                name = self._extract_name_from_title(title)
                if name and self._is_relevant(name, company_name, lower_combined):
                    names.add(name)
                    if "ceo" in lower_combined or "chief executive" in lower_combined:
                        roles[name] = "ceo"
                    elif any(kw in lower_combined for kw in ["founder", "co-founder", "cofounder"]):
                        roles[name] = "founder"

            # Extract names from general results mentioning founder/CEO keywords
            if any(kw in lower_combined for kw in ["founder", "co-founder", "cofounder", "ceo"]):
                extracted = self._extract_names_from_text(combined)
                for name in extracted:
                    lower_name = name.lower()
                    # Skip if name contains the company name or vice versa
                    if (lower_name == company_name.lower()
                            or company_name.lower() in lower_name
                            or lower_name in company_name.lower()):
                        continue
                    if self._is_valid_name(name):
                        names.add(name)
                        if "ceo" in lower_combined:
                            roles[name] = "ceo"
                        else:
                            roles[name] = "founder"

        return names, linkedin_urls, roles

    def _parse_knowledge_graph(self, kg):
        """Extract founder/CEO names from knowledge graph data."""
        names = set()
        roles = {}

        attrs = kg.get("attributes", {})

        # Check for founder attributes
        for key in ["Founder", "Founders", "Co-founders", "Founded by", "Co-Founders"]:
            if key in attrs:
                for name in self._split_names(attrs[key]):
                    if self._is_valid_name(name):
                        names.add(name)
                        roles[name] = "founder"

        # Check for CEO
        for key in ["CEO", "Chief executive officer", "Chief Executive Officer"]:
            if key in attrs:
                name = attrs[key].strip()
                if self._is_valid_name(name):
                    names.add(name)
                    roles[name] = "ceo"

        return names, roles

    def _extract_linkedin_urls(self, text):
        """Extract LinkedIn profile URLs from text."""
        pattern = r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_%-]+'
        return list(set(re.findall(pattern, text)))

    def _extract_name_from_title(self, title):
        """
        Extract a person's name from a LinkedIn-style title.
        e.g. "John Doe - Founder at Company | LinkedIn" -> "John Doe"
        """
        if not title:
            return None

        # Split on common delimiters
        parts = re.split(r'\s*[-–—|]\s*', title)
        if parts:
            name = parts[0].strip()
            # Validate it looks like a name (2-4 capitalized words)
            words = name.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                # Filter out common non-name words
                skip = {"LinkedIn", "Company", "Inc", "CEO", "The", "About", "Profile"}
                if not any(w in skip for w in words):
                    return name

        return None

    def _extract_names_from_text(self, text):
        """Extract person names (capitalized word pairs) from text."""
        names = []
        words = text.split()

        # Common words that appear capitalized but aren't names
        skip = {
            "The", "And", "For", "With", "From", "About", "This", "That",
            "Our", "Inc", "CEO", "CFO", "CTO", "COO", "Founded", "Company",
            "Series", "Read", "More", "LinkedIn", "Google", "Search", "Web",
            "New", "York", "San", "Los", "Chief", "Executive", "Officer",
            "Financial", "Product", "Management", "Team", "Key", "View",
            "Index", "Ventures", "Capital", "Partners", "Fund", "Group",
            "Board", "Directors", "Stock", "Exchange", "Forbes", "Wikipedia",
            "Business", "Insider", "Org", "Chart", "Bio", "Profile",
            "Meet", "Who", "How", "What", "Where", "When", "Why",
            "After", "Before", "During", "Between", "Under", "Over",
            "Also", "Just", "Only", "Most", "Some", "All", "Any",
            "University", "College", "Institute", "School", "Brown",
            "Stanford", "Harvard", "MIT", "Berkeley", "Explore",
            "Subscribe", "Follow", "Share", "Report", "Download",
            "Employs", "Goes", "Raised", "Funding", "Round", "Seed",
            "Early", "Stage", "Late", "Growth", "Venture", "Angel",
            "Market", "Industry", "Sector", "Global", "World",
            "North", "South", "East", "West", "Silicon", "Valley",
            "Visionaries", "Figures", "Leaders",
        }

        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i + 1]

            # Both words should be capitalized, purely alpha, and reasonable length
            if (w1 and w2 and w1[0].isupper() and w2[0].isupper()
                    and 2 <= len(w1) <= 12 and 2 <= len(w2) <= 15
                    and w1.isalpha() and w2.isalpha()):

                if w1 not in skip and w2 not in skip:
                    name = f"{w1} {w2}"
                    if name not in names and len(name) > 5:
                        names.append(name)

        return names

    def _split_names(self, text):
        """Split a string like 'John Doe, Jane Smith, and Bob Jones' into names."""
        # Remove "and"
        text = re.sub(r'\band\b', ',', text)
        parts = [p.strip() for p in text.split(',')]
        return [p for p in parts if p and len(p) > 2]

    def _match_linkedin(self, name, linkedin_urls):
        """Try to match a name to a LinkedIn URL from the collected URLs."""
        name_slug = name.lower().replace(" ", "-")
        name_parts = name.lower().split()

        # Exact or partial slug match
        for slug, url in linkedin_urls.items():
            if name_slug in slug or slug in name_slug:
                return url

        # Try matching individual name parts
        for slug, url in linkedin_urls.items():
            if all(part in slug for part in name_parts):
                return url

        return ""

    def _is_relevant(self, name, company_name, context):
        """Check if a name is relevant to the company (not just a random LinkedIn result)."""
        lower_name = name.lower()
        lower_company = company_name.lower()

        # Name shouldn't be the company name itself
        if lower_name == lower_company:
            return False

        # Context should mention the company or founder keywords
        if lower_company in context or "founder" in context or "ceo" in context:
            return True

        return False

    def _is_valid_name(self, name):
        """Validate that a string looks like a person's name."""
        if not name or len(name) < 4:
            return False

        words = name.split()
        if len(words) < 2 or len(words) > 4:
            return False

        # Should be mostly alphabetic
        alpha_chars = sum(c.isalpha() or c in (' ', '-', "'") for c in name)
        if alpha_chars / len(name) < 0.9:
            return False

        # Each word should be capitalized and reasonable length
        for w in words:
            if not w[0].isupper():
                return False
            if len(w) < 2 or len(w) > 15:
                return False

        # Reject if any word is a common non-name word
        skip_words = {
            "linkedin", "company", "inc", "llc", "corp", "founded", "startup",
            "chief", "executive", "officer", "financial", "product", "management",
            "team", "ventures", "capital", "partners", "university", "college",
            "index", "board", "directors", "stock", "exchange", "market",
            "wikipedia", "forbes", "business", "insider", "org", "chart",
            "key", "figures", "fund", "group", "visionaries", "explore",
            "news", "giant", "introduction", "behind", "success", "built",
            "payments", "founder", "leadership", "engineering", "manager",
            "street", "wall", "fellowship", "employs", "rocketreach",
            "billion", "million", "funding", "raised", "round", "series",
            "tech", "technology", "software", "hardware", "platform",
            "digital", "global", "world", "industry", "sector",
            "announced", "report", "today", "years", "year", "since",
            "crunchbase", "exclusive", "ghost", "shark", "tour", "here",
            "june", "july", "august", "september", "october", "november",
            "december", "january", "february", "march", "april", "may",
            "county", "orange", "angeles", "francisco", "technical",
            "producer", "reviews", "technologies", "industries",
            "oculus", "palantir", "pdf", "overview", "bloomberg",
            "billionaires", "trillion", "valuation", "acquisition",
            "acquired", "merger", "revenue", "profit", "income",
            "according", "reported", "sources", "confirmed",
        }
        if any(w.lower() in skip_words for w in words):
            return False

        # Reject compound words or overly long names
        if any(len(w) > 12 for w in words):
            return False

        return True

    def _load_founders(self):
        """Load founders.json."""
        with open(self.founders_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_founders(self, data):
        """Save founders.json."""
        with open(self.founders_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
