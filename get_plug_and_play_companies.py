#!/usr/bin/env python3
"""
Find Plug and Play portfolio companies using Serper API.
"""

import json
import os
import requests
import time
import re
from pathlib import Path

FIRMS_FILE = "/Users/ryanmurray/programming/vc/firms.json"
FOUNDERS_FILE = "/Users/ryanmurray/programming/vc/founders.json"
ENV_FILE = "/Users/ryanmurray/programming/vc/enricher/.env"

def load_api_key():
    """Load Serper API key from .env file."""
    if not os.path.exists(ENV_FILE):
        return None
    with open(ENV_FILE) as f:
        for line in f:
            if line.startswith("SERPER_API_KEY="):
                key = line.split("=", 1)[1].strip()
                if key and key != "your_api_key_here":
                    return key
    return None

def serper_search(query, api_key):
    """Search using Serper API."""
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    payload = {"q": query, "num": 20}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return None

def extract_company_names(text):
    """Extract company names from search results."""
    companies = []
    seen = set()

    # Look for patterns like "Company Name - " or "Company Name at Plug and Play"
    # Split by common separators
    parts = re.split(r'[-–|•]\s+', text)

    for part in parts:
        # Clean up the part
        part = part.strip()

        # Remove common noise words
        for noise in ['Plug and Play', 'portfolio', 'companies', 'portfolio company', 'is a', 'the', 'founded', 'startup', '|', '-']:
            part = part.replace(noise, '').strip()

        # Extract first meaningful phrase (usually company name)
        if len(part) > 2 and len(part) < 100 and part[0].isupper():
            # Remove trailing junk
            part = re.sub(r'\(.*?\)|, .*', '', part).strip()

            if len(part) > 2 and part.lower() not in seen:
                companies.append(part)
                seen.add(part.lower())

    return companies

def main():
    api_key = load_api_key()
    if not api_key:
        print("ERROR: Serper API key not found")
        return

    # Load files
    with open(FIRMS_FILE) as f:
        firms = json.load(f)

    with open(FOUNDERS_FILE) as f:
        founders = json.load(f)

    print("\n" + "="*70)
    print("Finding Plug and Play Portfolio Companies via Serper")
    print("="*70 + "\n")

    # Search for Plug and Play portfolio companies
    queries = [
        '"Plug and Play" portfolio companies list',
        '"Plug and Play" startups funded',
        '"Plug and Play" investments 2024 2025',
        'site:plugandplaytechcenter.com portfolio companies',
    ]

    all_companies = set()

    for query in queries:
        print(f"Searching: {query}")
        result = serper_search(query, api_key)

        if result and "organic" in result:
            for i, item in enumerate(result["organic"][:5]):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                combined = title + " " + snippet

                # Extract company names
                companies = extract_company_names(combined)
                for company in companies:
                    if len(company) > 2:
                        all_companies.add(company)

        time.sleep(0.5)

    # Clean up company names
    cleaned_companies = []
    for company in sorted(all_companies):
        company = company.strip()
        # Remove very generic names
        if company.lower() not in ['portfolio', 'companies', 'startups', 'company', 'the', 'and', 'or']:
            # Remove trailing description words
            company = re.sub(r'\s+(provides?|offers?|is a|develops?|makes?|creates?).*$', '', company, flags=re.IGNORECASE).strip()
            if len(company) > 2 and company not in cleaned_companies:
                cleaned_companies.append(company)

    print(f"\nFound {len(cleaned_companies)} companies")

    if cleaned_companies:
        print("\nPlug and Play Portfolio Companies:")
        for i, company in enumerate(cleaned_companies[:30], 1):
            print(f"  {i:2}. {company}")
        if len(cleaned_companies) > 30:
            print(f"  ... and {len(cleaned_companies) - 30} more")

    # Add to founders.json
    new_count = 0
    for company_name in cleaned_companies:
        if company_name not in founders:
            founders[company_name] = {
                "url": "",
                "founders": [],
                "ceo": {}
            }
            new_count += 1

    # Update firms.json with Plug and Play investments
    for firm in firms:
        if firm["name"] == "Plug and Play":
            firm["investments"] = [
                {"company": c, "url": ""} for c in cleaned_companies
            ]
            print(f"\nUpdated Plug and Play with {len(cleaned_companies)} investments")
            break

    # Save files
    with open(FIRMS_FILE, 'w') as f:
        json.dump(firms, f, indent=2)

    with open(FOUNDERS_FILE, 'w') as f:
        json.dump(founders, f, indent=2)

    print(f"Added {new_count} new companies to founders.json")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
