#!/usr/bin/env python3
"""
Scrape MA-area VC portfolio pages directly to extract company names.

Usage:
  python3 scrape_ma_vcs.py              # Run scraper
  python3 scrape_ma_vcs.py --dry-run    # Preview without writing
"""

import json
import os
import sys
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin

# --- Config ---
FIRMS_FILE = "/Users/ryanmurray/programming/vc/firms.json"
FOUNDERS_FILE = "/Users/ryanmurray/programming/vc/founders.json"
VC_TAGS_FILE = "/Users/ryanmurray/programming/vc/vc_tags.json"

MA_FIRMS = [
    {"name": "The Engine", "hq": "Cambridge, MA", "focus": ["deep tech"], "portfolio_url": "https://www.engine.xyz/portfolio"},
    {"name": "Clean Energy Ventures", "hq": "Boston, MA", "focus": ["energy tech", "green tech"], "portfolio_url": "https://www.cleanenergyventures.com/portfolio"},
    {"name": "Pillar VC", "hq": "Boston, MA", "focus": ["deep tech"], "portfolio_url": "https://www.pillar.vc/portfolio"},
    {"name": "Atlas Venture", "hq": "Cambridge, MA", "focus": ["deep tech"], "portfolio_url": "https://atlasventure.com/companies"},
    {"name": "Energy Impact Partners", "hq": "Boston, MA", "focus": ["energy tech"], "portfolio_url": "https://www.energyimpactpartners.com/portfolio"},
    {"name": "Activate Global", "hq": "Somerville, MA", "focus": ["deep tech"], "portfolio_url": "https://www.activate.org/fellows"},
    {"name": "Third Rock Ventures", "hq": "Boston, MA", "focus": ["deep tech"], "portfolio_url": "https://www.thirdrockventures.com/companies"},
    {"name": "Hyperplane", "hq": "Boston, MA", "focus": ["deep tech"], "portfolio_url": "https://hyperplane.vc/portfolio"},
    {"name": "Underscore VC", "hq": "Boston, MA", "focus": ["deep tech"], "portfolio_url": "https://underscore.vc/portfolio"},
    {"name": "MassVentures", "hq": "Waltham, MA", "focus": ["deep tech"], "portfolio_url": "https://www.massventures.com/portfolio"},
    {"name": "Prelude Ventures", "hq": "San Francisco, CA", "focus": ["green tech", "energy tech"], "portfolio_url": "https://www.preludeventures.com/portfolio"},
    {"name": "Congruent Ventures", "hq": "Oakland, CA", "focus": ["green tech", "energy tech"], "portfolio_url": "https://congruentvc.com/portfolio"},
    {"name": "Breakthrough Energy Ventures", "hq": "Kirkland, WA", "focus": ["green tech", "energy tech", "deep tech"], "portfolio_url": "https://www.breakthroughenergy.org/investing/ventures"},
    {"name": "Greentown Labs", "hq": "Somerville, MA", "focus": ["green tech", "energy tech"], "portfolio_url": "https://greentownlabs.com/member-companies"},
    {"name": "Prime Coalition", "hq": "Cambridge, MA", "focus": ["green tech", "energy tech"], "portfolio_url": "https://primecoalition.org/portfolio"},
]

# --- Helper Functions ---
def scrape_portfolio_page(url):
    """
    Scrape VC portfolio page and extract company names.
    Returns list of {"company": name, "url": url} dicts.
    """
    companies = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Strategy 1: Look for common portfolio link patterns
        # Companies are often in <a> tags with href patterns like /portfolio/company-name or /companies/name
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # Look for portfolio/companies in the path
            if any(pattern in href for pattern in ['/portfolio/', '/companies/', '/company/', '/startups/', '/member', '/fellows']):
                if text and len(text) > 2 and text.lower() not in ['read more', 'learn more', 'portfolio', 'companies', 'back']:
                    companies.append({"company": text, "url": urljoin(url, href)})

        # Strategy 2: Look for text in divs/sections with company names
        # Many portfolio pages have divs with class like 'company', 'portfolio-item', 'portfolio-card', etc.
        for selector in ['.portfolio-item', '.company', '.portfolio-card', '.startup', '.member-company', '.portfolio-company', '[data-company]']:
            for elem in soup.select(selector):
                # Get the text content
                text = elem.get_text(strip=True)
                if text and len(text) > 2 and len(text) < 100:
                    # Also try to get a link if it exists
                    link = elem.find('a', href=True)
                    company_url = urljoin(url, link.get('href', '')) if link else ''
                    companies.append({"company": text, "url": company_url})

        # Strategy 3: Look for headings (h2, h3, h4) that might be company names
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            text = heading.get_text(strip=True)
            if text and 3 < len(text) < 80 and text[0].isupper():
                companies.append({"company": text, "url": ""})

        # Deduplicate by company name (case-insensitive)
        seen = {}
        deduped = []
        for comp in companies:
            key = comp["company"].lower().strip()
            if key not in seen and len(key) > 2:
                seen[key] = True
                deduped.append(comp)

        return deduped

    except Exception as e:
        print(f"  ERROR scraping {url}: {e}")
        return []

def load_json(filepath):
    """Load JSON file."""
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    return {} if "tags" in filepath or "founders" in filepath else []

def save_json(filepath, data):
    """Save JSON file with indentation."""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved {filepath}")

def is_ma_presence(hq):
    """Check if HQ location ends with ', MA'."""
    return hq.endswith(", MA")

def run_scraper(dry_run=False):
    """Main scraper logic."""
    firms_data = load_json(FIRMS_FILE)
    founders_data = load_json(FOUNDERS_FILE)
    vc_tags_data = load_json(VC_TAGS_FILE)

    print(f"\n{'='*60}")
    print(f"MA VC Portfolio Scraper")
    print(f"{'='*60}")
    print(f"Dry-run mode: {dry_run}")
    print(f"Current firms: {len(firms_data)}")
    print(f"Current companies: {len(founders_data)}")

    new_firms_count = 0
    new_companies_count = 0

    for firm_config in MA_FIRMS:
        firm_name = firm_config["name"]
        portfolio_url = firm_config.get("portfolio_url")
        print(f"\n--- {firm_name} ---")
        print(f"URL: {portfolio_url}")

        # Check if firm already exists
        firm_exists = any(f["name"] == firm_name for f in firms_data)
        print(f"Exists in firms.json: {firm_exists}")

        # Scrape portfolio page
        companies = scrape_portfolio_page(portfolio_url)
        print(f"Found {len(companies)} companies")

        # Add companies to founders.json if not present
        for company in companies:
            company_name = company["company"].strip()
            # Filter out generic/structural text
            if len(company_name) > 2 and company_name.lower() not in [
                'portfolio', 'companies', 'our companies', 'startups', 'team', 'about',
                'contact', 'news', 'careers', 'home', 'invest', 'apply', 'more info',
                'learn more', 'read more', 'follow', 'view', 'visit', 'link'
            ]:
                if company_name not in founders_data:
                    founders_data[company_name] = {
                        "url": company.get("url", ""),
                        "founders": [],
                        "ceo": {}
                    }
                    new_companies_count += 1
                    print(f"  + {company_name}")

        # Upsert firm into firms.json
        investment_list = [
            {"company": c["company"].strip(), "url": c.get("url", "")}
            for c in companies
            if c["company"].strip().lower() not in [
                'portfolio', 'companies', 'our companies', 'startups', 'team', 'about',
                'contact', 'news', 'careers', 'home', 'invest', 'apply', 'more info',
                'learn more', 'read more', 'follow', 'view', 'visit', 'link'
            ]
        ]

        if not firm_exists:
            firms_data.append({
                "name": firm_name,
                "country": "United States",
                "investments": investment_list
            })
            new_firms_count += 1
            print(f"Added {firm_name} with {len(investment_list)} investments")
        else:
            # Update existing firm
            for firm in firms_data:
                if firm["name"] == firm_name:
                    firm["investments"] = investment_list
                    print(f"Updated {firm_name} with {len(investment_list)} investments")
                    break

        # Update vc_tags.json
        ma_presence = is_ma_presence(firm_config["hq"])
        vc_tags_data[firm_name] = {
            "focus": firm_config["focus"],
            "ma_presence": ma_presence,
            "hq": firm_config["hq"]
        }

        # Small delay to be respectful
        time.sleep(0.5)

    if not dry_run:
        save_json(FIRMS_FILE, firms_data)
        save_json(FOUNDERS_FILE, founders_data)
        save_json(VC_TAGS_FILE, vc_tags_data)
        print(f"\n{'='*60}")
        print(f"Scrape Complete!")
        print(f"New firms added: {new_firms_count}")
        print(f"New companies added: {new_companies_count}")
        print(f"Total firms now: {len(firms_data)}")
        print(f"Total companies now: {len(founders_data)}")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print(f"DRY-RUN: Would add {new_firms_count} firms and {new_companies_count} companies")
        print(f"{'='*60}")

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_scraper(dry_run=dry_run)
