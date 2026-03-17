#!/usr/bin/env python3
"""
Scrape Plug and Play's portfolio companies and add to database.
"""

import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import time
import re
from urllib.parse import urljoin

FIRMS_FILE = "/Users/ryanmurray/programming/vc/firms.json"
FOUNDERS_FILE = "/Users/ryanmurray/programming/vc/founders.json"

def scrape_plug_and_play_portfolio():
    """Scrape Plug and Play's portfolio page for company names."""
    url = "https://www.plugandplaytechcenter.com/portfolio/"

    companies = []
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        print(f"Scraping {url}")
        print(f"Status: {response.status_code}")

        # Strategy 1: Look for company cards/items
        # Plug and Play typically has company names in divs with specific classes
        for selector in ['.company-card', '.portfolio-item', '.company-name', '[class*="company"]', '[class*="portfolio"]']:
            for elem in soup.select(selector):
                text = elem.get_text(strip=True)

                # Look for links that might have company URLs
                link = elem.find('a', href=True)
                company_url = link['href'] if link else ""

                if text and len(text) > 2 and len(text) < 100:
                    companies.append({"company": text, "url": company_url})

        # Strategy 2: Extract from text content - look for capitalized names
        # that appear in portfolio context
        all_text = soup.get_text()

        # Strategy 3: Look for company links in the page
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # Look for portfolio company links
            if any(pattern in href for pattern in ['/portfolio/', '/company/', '/companies/', '/startups/']):
                if text and len(text) > 2 and text.lower() not in ['read more', 'learn more', 'portfolio', 'companies', 'back']:
                    companies.append({"company": text, "url": urljoin(url, href)})

        # Deduplicate
        seen = {}
        deduped = []
        for comp in companies:
            key = comp["company"].lower().strip()
            if key not in seen and len(key) > 2:
                seen[key] = True
                deduped.append(comp)

        return deduped

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return []

def main():
    # Load files
    with open(FIRMS_FILE) as f:
        firms = json.load(f)

    with open(FOUNDERS_FILE) as f:
        founders = json.load(f)

    print("\n" + "="*70)
    print("Scraping Plug and Play Portfolio")
    print("="*70 + "\n")

    # Scrape portfolio
    companies = scrape_plug_and_play_portfolio()
    print(f"Found {len(companies)} companies from Plug and Play portfolio\n")

    # Show sample
    if companies:
        print("Sample companies:")
        for comp in companies[:10]:
            print(f"  • {comp['company']}")
        if len(companies) > 10:
            print(f"  ... and {len(companies) - 10} more")

    # Add to founders.json if not present
    new_count = 0
    for company in companies:
        company_name = company["company"].strip()

        # Filter out generic text
        if len(company_name) > 2 and company_name.lower() not in [
            'portfolio', 'companies', 'startups', 'team', 'about',
            'home', 'back', 'more', 'view', 'visit'
        ]:
            if company_name not in founders:
                founders[company_name] = {
                    "url": company.get("url", ""),
                    "founders": [],
                    "ceo": {}
                }
                new_count += 1

    # Update Plug and Play's investments in firms.json
    for firm in firms:
        if firm["name"] == "Plug and Play":
            firm["investments"] = [
                {"company": c["company"].strip(), "url": c.get("url", "")}
                for c in companies
                if c["company"].strip().lower() not in [
                    'portfolio', 'companies', 'startups', 'team', 'about',
                    'home', 'back', 'more', 'view', 'visit'
                ]
            ]
            print(f"Updated Plug and Play with {len(firm['investments'])} investments\n")
            break

    # Save files
    with open(FIRMS_FILE, 'w') as f:
        json.dump(firms, f, indent=2)

    with open(FOUNDERS_FILE, 'w') as f:
        json.dump(founders, f, indent=2)

    print("="*70)
    print(f"Added {new_count} new companies to founders.json")
    print(f"Saved {FIRMS_FILE}")
    print(f"Saved {FOUNDERS_FILE}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
