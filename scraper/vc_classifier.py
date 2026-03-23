"""
VC firm investment thesis classifier.
Searches for each VC's investment focus and assigns sector/stage/geography tags.
Enables filtering like "show me all biotech seed-stage VCs".
"""

import json
import re
import time
import logging
from pathlib import Path

from scraper import MultiScraper

logger = logging.getLogger(__name__)

DEFAULT_VC_TAGS_PATH = Path(__file__).parent.parent / "vc-main" / "vc_tags.json"

# Sector taxonomy — keywords that map to each sector
SECTOR_KEYWORDS = {
    "AI / Machine Learning": [
        "artificial intelligence", "machine learning", "deep learning",
        "ai-first", "ai native", "generative ai", "computer vision",
        "natural language processing", "nlp", "robotics", "autonomous",
    ],
    "Biotech / Life Sciences": [
        "biotech", "biotechnology", "life science", "pharmaceutical",
        "drug discovery", "genomics", "therapeutics", "biopharma",
        "clinical trial", "diagnostics", "precision medicine",
    ],
    "Healthcare": [
        "healthcare", "health tech", "healthtech", "digital health",
        "medical device", "telemedicine", "telehealth", "patient care",
        "health insurance", "mental health", "wellness",
    ],
    "Fintech": [
        "fintech", "financial technology", "payments", "banking",
        "insurance tech", "insurtech", "lending", "neobank",
        "defi", "financial services", "wealth management",
    ],
    "Climate / Energy": [
        "climate", "clean energy", "renewable", "solar", "wind",
        "energy transition", "decarbonization", "carbon", "sustainability",
        "green tech", "cleantech", "energy storage", "battery",
        "hydrogen", "nuclear", "fusion", "grid",
    ],
    "SaaS / Enterprise": [
        "saas", "enterprise software", "b2b software", "cloud",
        "developer tools", "devtools", "infrastructure software",
        "productivity", "workflow", "collaboration",
    ],
    "Consumer": [
        "consumer", "d2c", "direct to consumer", "e-commerce",
        "ecommerce", "marketplace", "social media", "gaming",
        "entertainment", "media", "consumer tech", "retail",
    ],
    "Industrials / Manufacturing": [
        "industrial", "manufacturing", "supply chain", "logistics",
        "construction", "materials", "mining", "aerospace",
        "defense", "industrial tech", "automation", "iot",
    ],
    "Crypto / Web3": [
        "crypto", "blockchain", "web3", "defi", "nft",
        "decentralized", "token", "digital asset",
    ],
    "Real Estate / PropTech": [
        "real estate", "proptech", "property tech", "construction tech",
        "housing", "commercial real estate",
    ],
    "Food / Agriculture": [
        "food", "agriculture", "agtech", "agritech", "farming",
        "food tech", "foodtech", "alternative protein", "vertical farming",
    ],
    "Education": [
        "education", "edtech", "learning", "online education",
        "skill development", "training",
    ],
    "Cybersecurity": [
        "cybersecurity", "security", "infosec", "data protection",
        "identity", "zero trust", "threat detection",
    ],
    "Deep Tech / Frontier": [
        "deep tech", "frontier tech", "hard tech", "quantum",
        "space", "satellite", "advanced materials", "nanotechnology",
    ],
}

# Stage keywords
STAGE_KEYWORDS = {
    "Pre-Seed / Seed": [
        "pre-seed", "preseed", "seed stage", "seed fund",
        "earliest stage", "idea stage", "inception",
    ],
    "Early Stage": [
        "early stage", "early-stage", "series a", "series b",
        "seed and series a", "startup", "emerging",
    ],
    "Growth": [
        "growth stage", "growth equity", "growth-stage",
        "series c", "series d", "scale-up", "expansion",
    ],
    "Late Stage": [
        "late stage", "late-stage", "pre-ipo", "crossover",
        "series e", "series f", "mezzanine",
    ],
    "Multi-Stage": [
        "multi-stage", "all stages", "seed to growth",
        "early to growth", "full lifecycle",
    ],
}

# Geography keywords
GEO_KEYWORDS = {
    "US": ["united states", "us-based", "silicon valley", "new york", "boston", "san francisco"],
    "Europe": ["europe", "european", "uk", "london", "berlin", "paris", "nordic"],
    "Global": ["global", "worldwide", "international", "cross-border"],
    "Asia": ["asia", "china", "india", "southeast asia", "japan", "korea"],
    "Emerging Markets": ["emerging market", "africa", "latin america", "middle east"],
}


class VCClassifier:
    """Classifies VC firms by sector, stage, and geography."""

    def __init__(self, vc_tags_path=None):
        self.vc_tags_path = Path(vc_tags_path) if vc_tags_path else DEFAULT_VC_TAGS_PATH
        self.scraper = MultiScraper()
        self.progress = {
            "status": "idle",
            "total": 0,
            "processed": 0,
            "classified": 0,
            "current_firm": "",
        }

    def get_unclassified_firms(self):
        """Return firm names that only have generic tags."""
        tags = self._load_tags()
        generic = {"venture capital", "unknown", "general", "deep tech",
                    "green tech", "clean energy", "energy tech", "energy",
                    "climate", "infrastructure", "ai"}
        unclassified = []
        for name, meta in tags.items():
            existing = set(meta.get("focus", []))
            if not existing or existing.issubset(generic):
                unclassified.append(name)
        return unclassified

    def classify_firm(self, firm_name, website_url=None):
        """
        Classify a single VC firm's investment focus.

        Returns:
            dict with "sectors", "stages", "geography" lists
        """
        # Build search text from multiple sources
        search_text = ""

        # Query 1: Investment thesis
        result = self.scraper.search(f'"{firm_name}" investment thesis focus sectors')
        if result:
            for r in result.get("organic", [])[:5]:
                search_text += f" {r.get('title', '')} {r.get('snippet', '')}"

        # Query 2: About page / description
        result2 = self.scraper.search(f'"{firm_name}" venture capital invests in')
        if result2:
            for r in result2.get("organic", [])[:5]:
                search_text += f" {r.get('title', '')} {r.get('snippet', '')}"

        if not search_text.strip():
            return None

        lower_text = search_text.lower()

        # Match sectors
        sectors = []
        for sector, keywords in SECTOR_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in lower_text)
            if matches >= 2:  # Need at least 2 keyword hits
                sectors.append((matches, sector))

        sectors.sort(key=lambda x: -x[0])
        sector_names = [s[1] for s in sectors[:4]]  # Top 4 sectors max

        # Match stages
        stages = []
        for stage, keywords in STAGE_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in lower_text)
            if matches >= 1:
                stages.append((matches, stage))

        stages.sort(key=lambda x: -x[0])
        stage_names = [s[1] for s in stages[:2]]  # Top 2 stages max

        # Match geography
        geos = []
        for geo, keywords in GEO_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in lower_text)
            if matches >= 1:
                geos.append((matches, geo))

        geos.sort(key=lambda x: -x[0])
        geo_names = [g[1] for g in geos[:2]]

        if not sector_names and not stage_names:
            return None

        return {
            "sectors": sector_names,
            "stages": stage_names,
            "geography": geo_names,
        }

    def classify_batch(self, limit=None, dry_run=False, callback=None):
        """Classify all unclassified firms."""
        tags = self._load_tags()
        unclassified = self.get_unclassified_firms()

        if limit:
            unclassified = unclassified[:limit]

        self.progress = {
            "status": "running",
            "total": len(unclassified),
            "processed": 0,
            "classified": 0,
            "current_firm": "",
            "results": [],
        }

        for i, firm_name in enumerate(unclassified):
            self.progress["current_firm"] = firm_name
            self.progress["processed"] = i

            if callback:
                callback(self.progress)

            website = tags.get(firm_name, {}).get("website", "")
            logger.info(f"[{i+1}/{len(unclassified)}] Classifying: {firm_name}")

            try:
                classification = self.classify_firm(firm_name, website)

                if classification:
                    self.progress["classified"] += 1
                    self.progress["results"].append({
                        "firm": firm_name,
                        "sectors": classification["sectors"],
                        "stages": classification["stages"],
                        "geography": classification["geography"],
                    })

                    sectors_str = ", ".join(classification["sectors"][:3])
                    logger.info(f"  Sectors: {sectors_str}")

                    if not dry_run:
                        # Update the focus field with rich sector tags
                        tags[firm_name]["sectors"] = classification["sectors"]
                        tags[firm_name]["stages"] = classification["stages"]
                        tags[firm_name]["geography"] = classification["geography"]
                        self._save_tags(tags)
                else:
                    logger.info(f"  Could not classify")

            except Exception as e:
                logger.error(f"  Error: {e}")

        self.progress["processed"] = len(unclassified)
        self.progress["status"] = "completed"
        self.progress["current_firm"] = ""

        if callback:
            callback(self.progress)

        return self.progress

    def _load_tags(self):
        with open(self.vc_tags_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_tags(self, data):
        with open(self.vc_tags_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
