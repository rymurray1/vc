#!/usr/bin/env python3
"""
Add energy VC firms from Failory article.
Finds founder LinkedIn profiles and merges into database.
"""

import json
import os
import sys
import requests
import time
import re
from pathlib import Path

# --- Config ---
FIRMS_FILE = "/Users/ryanmurray/programming/vc/firms.json"
FOUNDERS_FILE = "/Users/ryanmurray/programming/vc/founders.json"
VC_TAGS_FILE = "/Users/ryanmurray/programming/vc/vc_tags.json"
ENV_FILE = "/Users/ryanmurray/programming/vc/enricher/.env"

# Energy VC firms from Failory article
ENERGY_VACS = [
    {"name": "Plug and Play", "hq": "Sunnyvale, California", "country": "United States", "founders": ["Ali Safavi", "Saeed Amidi"], "focus": ["energy tech", "deep tech"], "website": "plugandplaytechcenter.com"},
    {"name": "Draper Associates", "hq": "San Mateo, California", "country": "United States", "founders": ["Tim Draper"], "focus": ["energy tech", "deep tech"], "website": "draper.vc"},
    {"name": "Eclipse Ventures", "hq": "Palo Alto, California", "country": "United States", "founders": ["Lior Susan"], "focus": ["energy tech", "deep tech"], "website": "eclipse.capital"},
    {"name": "Lux Capital", "hq": "New York, New York", "country": "United States", "founders": ["Josh Wolfe", "Peter Hebert"], "focus": ["energy tech", "deep tech"], "website": "luxcapital.com"},
    {"name": "Correlation Ventures", "hq": "San Diego, California", "country": "United States", "founders": ["David Coats", "Trevor Kienzle"], "focus": ["energy tech"], "website": "correlationvc.com"},
    {"name": "Heartcore Capital", "hq": "Copenhagen, Denmark", "country": "Denmark", "founders": ["Christian Jepsen", "Jimmy Nielsen"], "focus": ["energy tech"], "website": "heartcore.com"},
    {"name": "Contrarian Ventures", "hq": "Vilnius, Lithuania", "country": "Lithuania", "founders": ["Marc Wesselink", "Nityen Lal"], "focus": ["energy tech", "green tech"], "website": "cventures.vc"},
    {"name": "IDG Capital", "hq": "Beijing, China", "country": "China", "founders": [], "focus": ["energy tech"], "website": "cn.idgcapital.com"},
    {"name": "Airtree Ventures", "hq": "Surry Hills, Australia", "country": "Australia", "founders": ["Craig Blair", "Daniel Petre"], "focus": ["energy tech"], "website": "airtree.vc"},
    {"name": "Playfair Capital", "hq": "London, England", "country": "United Kingdom", "founders": ["Federico Pirzio-Biroli"], "focus": ["energy tech"], "website": "playfair.vc"},
    {"name": "BDC Venture Capital", "hq": "Canada", "country": "Canada", "founders": [], "focus": ["energy tech"], "website": "bdc.ca"},
    {"name": "Future Energy Ventures", "hq": "Germany", "country": "Germany", "founders": [], "focus": ["energy tech", "green tech"], "website": "fev.vc"},
    {"name": "Kapor Capital", "hq": "United States", "country": "United States", "founders": [], "focus": ["energy tech"], "website": "kaporcapital.com"},
    {"name": "Icebreaker.vc", "hq": "Finland", "country": "Finland", "founders": [], "focus": ["energy tech", "green tech"], "website": "icebreaker.vc"},
    {"name": "Partech", "hq": "France", "country": "France", "founders": [], "focus": ["energy tech"], "website": "partechpartners.com"},
    {"name": "Boost VC", "hq": "United States", "country": "United States", "founders": [], "focus": ["energy tech"], "website": "boost.vc"},
    {"name": "Panache Ventures", "hq": "Canada", "country": "Canada", "founders": [], "focus": ["energy tech"], "website": "panache.vc"},
    {"name": "Axon Partners Group", "hq": "Spain", "country": "Spain", "founders": [], "focus": ["energy tech"], "website": "axonpartnersgroup.com"},
    {"name": "Mercury", "hq": "United States", "country": "United States", "founders": [], "focus": ["energy tech"], "website": "mercuryfund.com"},
    {"name": "Emerald Technology Ventures", "hq": "Switzerland", "country": "Switzerland", "founders": [], "focus": ["energy tech", "green tech"], "website": "emerald.vc"},
    {"name": "HCVC", "hq": "France", "country": "France", "founders": [], "focus": ["energy tech"], "website": "hcvc.co"},
    {"name": "Lemnos VC", "hq": "United States", "country": "United States", "founders": [], "focus": ["energy tech"], "website": "lemnos.vc"},
    {"name": "Fortune Venture Capital", "hq": "China", "country": "China", "founders": [], "focus": ["energy tech"], "website": "fortunevc.com"},
    {"name": "SHIFT Invest", "hq": "Netherlands", "country": "Netherlands", "founders": [], "focus": ["energy tech", "green tech"], "website": "shiftinvest.com"},
    {"name": "Cortado Ventures", "hq": "United States", "country": "United States", "founders": [], "focus": ["energy tech"], "website": "cortado.ventures"},
    {"name": "Cycle Capital", "hq": "Canada", "country": "Canada", "founders": [], "focus": ["energy tech", "green tech"], "website": "cyclecapital.com"},
    {"name": "Frontier Venture Capital", "hq": "United States", "country": "United States", "founders": [], "focus": ["energy tech"], "website": "frontiervc.com"},
    {"name": "Startuplab", "hq": "Norway", "country": "Norway", "founders": [], "focus": ["energy tech"], "website": "startuplab.no"},
    {"name": "ArcTern Ventures", "hq": "Canada", "country": "Canada", "founders": [], "focus": ["energy tech", "green tech"], "website": "arcternventures.com"},
    {"name": "Inven Capital", "hq": "Czech Republic", "country": "Czech Republic", "founders": [], "focus": ["energy tech"], "website": "invencapital.cz"},
    {"name": "Industrifonden", "hq": "Sweden", "country": "Sweden", "founders": [], "focus": ["energy tech"], "website": "industrifonden.com"},
]

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
    payload = {"q": query, "num": 10}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return None

def extract_linkedin_urls(text):
    """Extract LinkedIn profile URLs from text."""
    linkedin_pattern = r'https://linkedin\.com/in/[a-zA-Z0-9\-]+'
    return re.findall(linkedin_pattern, text)

def find_founder_linkedin(founder_name, api_key):
    """Find LinkedIn profile for a founder."""
    query = f"{founder_name} linkedin"
    serper_data = serper_search(query, api_key)

    if not serper_data or "organic" not in serper_data:
        return ""

    for result in serper_data.get("organic", [])[:3]:
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        url = result.get("link", "")

        linkedin_urls = extract_linkedin_urls(title + " " + snippet + " " + url)
        if linkedin_urls:
            return linkedin_urls[0]

    return ""

def main():
    # Load API key
    api_key = load_api_key()
    if not api_key:
        print("ERROR: Serper API key not found")
        sys.exit(1)

    # Load existing data
    with open(FIRMS_FILE) as f:
        firms = json.load(f)

    with open(VC_TAGS_FILE) as f:
        vc_tags = json.load(f)

    with open(FOUNDERS_FILE) as f:
        founders = json.load(f)

    existing_firms = {f["name"].lower() for f in firms}

    print(f"\n{'='*70}")
    print(f"Adding Energy VC Firms from Failory")
    print(f"{'='*70}")
    print(f"Existing firms: {len(existing_firms)}")
    print(f"Firms to process: {len(ENERGY_VACS)}\n")

    added_count = 0
    skipped_count = 0

    for vc in ENERGY_VACS:
        firm_name = vc["name"]

        # Check if already exists
        if firm_name.lower() in existing_firms:
            print(f"⊘ {firm_name} - already in database")
            skipped_count += 1
            continue

        print(f"✓ {firm_name} ({vc['hq']})", end="")

        # Find founder LinkedIn profiles if not provided
        founder_list = []
        for founder_name in vc.get("founders", []):
            linkedin_url = find_founder_linkedin(founder_name, api_key)
            founder_list.append({
                "name": founder_name,
                "linkedin": linkedin_url
            })
            time.sleep(0.3)  # Respectful delay

        # Add to firms.json
        firms.append({
            "name": firm_name,
            "country": vc.get("country", ""),
            "investments": []
        })

        # Add to vc_tags.json
        vc_tags[firm_name] = {
            "focus": vc.get("focus", ["energy tech"]),
            "ma_presence": "Massachusetts" in vc.get("hq", "") or ", MA" in vc.get("hq", ""),
            "hq": vc.get("hq", ""),
            "website": vc.get("website", "")
        }

        # Create placeholder in founders.json if not exists
        # (actual company list would come from portfolio scraping)

        added_count += 1
        print(f" - {len(founder_list)} founders found")
        time.sleep(0.5)

    # Save updated files
    with open(FIRMS_FILE, "w") as f:
        json.dump(firms, f, indent=2)

    with open(VC_TAGS_FILE, "w") as f:
        json.dump(vc_tags, f, indent=2)

    with open(FOUNDERS_FILE, "w") as f:
        json.dump(founders, f, indent=2)

    print(f"\n{'='*70}")
    print(f"Added: {added_count} new firms")
    print(f"Skipped: {skipped_count} (already in database)")
    print(f"Total firms now: {len(firms)}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
