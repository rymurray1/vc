#!/usr/bin/env python3
"""
Scrape Ridgeline VC portfolio from their website.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import time

FIRMS_FILE = "/Users/ryanmurray/programming/vc/firms.json"
FOUNDERS_FILE = "/Users/ryanmurray/programming/vc/founders.json"
VC_TAGS_FILE = "/Users/ryanmurray/programming/vc/vc_tags.json"

def scrape_ridgeline_portfolio():
    """Scrape Ridgeline VC's portfolio page."""
    url = "https://www.ridgeline.vc/portfolio"

    companies = []
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        print(f"Scraping {url}")
        print(f"Status: {response.status_code}\n")

        # Look for company links and names in various selectors
        for selector in ['.company', '.portfolio-item', '[class*="company"]', '[class*="portfolio"]', 'a[href*="portfolio"]']:
            for elem in soup.select(selector):
                text = elem.get_text(strip=True)
                link = elem.find('a', href=True)
                company_url = link['href'] if link else ""

                if text and len(text) > 2 and len(text) < 100:
                    companies.append({"company": text, "url": company_url})

        # Also look for company names in headings
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            text = heading.get_text(strip=True)
            if text and len(text) > 2 and len(text) < 80 and text[0].isupper():
                companies.append({"company": text, "url": ""})

        # Look for links that might be companies
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)

            if any(pattern in href for pattern in ['/portfolio/', '/companies/', '/company/']):
                if text and len(text) > 2 and text.lower() not in ['read more', 'learn more', 'portfolio']:
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

    with open(VC_TAGS_FILE) as f:
        vc_tags = json.load(f)

    print("="*70)
    print("Scraping Ridgeline VC Portfolio")
    print("="*70 + "\n")

    # Scrape portfolio
    companies = scrape_ridgeline_portfolio()
    print(f"Found {len(companies)} companies from Ridgeline VC\n")

    if companies:
        print("Sample companies:")
        for comp in companies[:15]:
            print(f"  • {comp['company']}")
        if len(companies) > 15:
            print(f"  ... and {len(companies) - 15} more\n")

    # Add to founders.json if not present
    new_count = 0
    for company in companies:
        company_name = company["company"].strip()

        # Filter out generic text
        if len(company_name) > 2 and company_name.lower() not in [
            'portfolio', 'companies', 'startups', 'team', 'about',
            'home', 'back', 'more', 'view', 'visit', 'contact'
        ]:
            if company_name not in founders:
                founders[company_name] = {
                    "url": company.get("url", ""),
                    "founders": [],
                    "ceo": {}
                }
                new_count += 1

    # Add/Update Ridgeline in firms.json
    ridgeline_exists = any(f["name"] == "Ridgeline VC" for f in firms)

    if not ridgeline_exists:
        firms.append({
            "name": "Ridgeline VC",
            "country": "United States",
            "investments": [
                {"company": c["company"].strip(), "url": c.get("url", "")}
                for c in companies
                if c["company"].strip().lower() not in [
                    'portfolio', 'companies', 'startups', 'team', 'about',
                    'home', 'back', 'more', 'view', 'visit', 'contact'
                ]
            ]
        })
        print(f"Added Ridgeline VC with {len(companies)} investments\n")
    else:
        for firm in firms:
            if firm["name"] == "Ridgeline VC":
                firm["investments"] = [
                    {"company": c["company"].strip(), "url": c.get("url", "")}
                    for c in companies
                    if c["company"].strip().lower() not in [
                        'portfolio', 'companies', 'startups', 'team', 'about',
                        'home', 'back', 'more', 'view', 'visit', 'contact'
                    ]
                ]
                print(f"Updated Ridgeline VC with {len(companies)} investments\n")
                break

    # Add to vc_tags.json
    vc_tags["Ridgeline VC"] = {
        "focus": ["deep tech", "infrastructure"],
        "ma_presence": False,
        "hq": "San Francisco, California",
        "website": "ridgeline.vc"
    }

    # Save files
    with open(FIRMS_FILE, 'w') as f:
        json.dump(firms, f, indent=2)

    with open(FOUNDERS_FILE, 'w') as f:
        json.dump(founders, f, indent=2)

    with open(VC_TAGS_FILE, 'w') as f:
        json.dump(vc_tags, f, indent=2)

    print("="*70)
    print(f"Added {new_count} new companies to founders.json")
    print(f"Total firms now: {len(firms)}")
    print(f"Total companies now: {len(founders)}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
