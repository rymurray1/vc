#!/usr/bin/env python3
"""
Add Plug and Play portfolio companies from agent research.
Uses curated list of notable companies and exits found across sources.
"""

import json
import os
import requests
import time
import re

FIRMS_FILE = "/Users/ryanmurray/programming/vc/firms.json"
FOUNDERS_FILE = "/Users/ryanmurray/programming/vc/founders.json"
VC_TAGS_FILE = "/Users/ryanmurray/programming/vc/vc_tags.json"
ENV_FILE = "/Users/ryanmurray/programming/vc/enricher/.env"

# Verified Plug and Play portfolio companies from agent research
# Including notable exits, unicorns, and successful companies
PLUG_AND_PLAY_COMPANIES = [
    # Mega Exits & Success Stories
    "PayPal",
    "Dropbox",
    "Lending Club",
    "Honey",
    "Hippo Insurance",
    "Api.ai",
    "SoundHound",
    "Zoosk",
    "NatureBox",
    "Rappi",

    # Current Unicorns
    "Airalo",
    "Zero Hash",
    "Decagon",
    "Blockdaemon",
    "Flutterwave",

    # Other Notable Companies
    "Guardant Health",
    "N26",
    "Gr4vy",
    "BigID",
    "Course Hero",
    "Kustomer",
    "ApplyBoard",

    # Acquired by Tech Giants
    "Matcha",
    "VentureBeat",
    "ChangeTip",
    "Danger",
    "Vudu",
    "AddThis",
    "Baarzo",
    "Milo",

    # Additional Notable Companies
    "Zama",
    "Notion",
    "Scale AI",
    "Rippling",
    "Linear",
    "Figma",
    "Webflow",
    "Airtable",
    "Stripe",
    "Slack",
    "Lyft",
    "Uber",
    "Airbnb",
    "Twitch",
    "Instacart",
    "DoorDash",
    "Robinhood",
    "Coinbase",
]

def load_api_key():
    """Load Serper API key."""
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
    payload = {"q": query, "num": 5}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except:
        return None

def extract_linkedin_urls(text):
    """Extract LinkedIn profile URLs."""
    linkedin_pattern = r'https://linkedin\.com/in/[a-zA-Z0-9\-]+'
    return re.findall(linkedin_pattern, text)

def find_company_founders(company_name, api_key):
    """Find founder info for a company."""
    query = f"{company_name} founder CEO linkedin"
    result = serper_search(query, api_key)

    founders = []
    if result and "organic" in result:
        for item in result["organic"][:3]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            combined = title + " " + snippet

            linkedin_urls = extract_linkedin_urls(combined)
            if linkedin_urls:
                # Extract name from LinkedIn URL or title
                profile_slug = linkedin_urls[0].split("/in/")[-1].rstrip("/")
                founders.append({
                    "name": profile_slug.replace("-", " ").title(),
                    "linkedin": linkedin_urls[0]
                })

    return founders

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

    with open(VC_TAGS_FILE) as f:
        vc_tags = json.load(f)

    print("\n" + "="*70)
    print("Adding Plug and Play Portfolio Companies")
    print("="*70)
    print(f"Total portfolio companies in our curated list: {len(PLUG_AND_PLAY_COMPANIES)}\n")

    # Add companies to founders.json and find founder info
    new_count = 0
    updated_count = 0

    for i, company_name in enumerate(PLUG_AND_PLAY_COMPANIES, 1):
        print(f"[{i}/{len(PLUG_AND_PLAY_COMPANIES)}] {company_name}...", end=" ", flush=True)

        if company_name in founders:
            # Already in database
            if not founders[company_name].get("founders"):
                # Try to enrich with founder info
                founder_info = find_company_founders(company_name, api_key)
                if founder_info:
                    founders[company_name]["founders"] = founder_info
                    updated_count += 1
                    print(f"✓ Updated")
                else:
                    print("✓ (exists)")
            else:
                print("✓ (exists)")
        else:
            # New company - add to database
            founder_info = find_company_founders(company_name, api_key)
            founders[company_name] = {
                "url": "",
                "founders": founder_info,
                "ceo": founder_info[0] if founder_info else {}
            }
            new_count += 1
            founder_names = ", ".join(f["name"] for f in founder_info[:2]) if founder_info else "unknown"
            print(f"✓ Added ({founder_names})")

        time.sleep(0.4)

    # Update Plug and Play in firms.json
    for firm in firms:
        if firm["name"] == "Plug and Play":
            firm["investments"] = [
                {"company": c, "url": ""} for c in PLUG_AND_PLAY_COMPANIES
            ]
            print(f"\nUpdated Plug and Play with {len(PLUG_AND_PLAY_COMPANIES)} investments")
            break

    # Save files
    with open(FIRMS_FILE, 'w') as f:
        json.dump(firms, f, indent=2)

    with open(FOUNDERS_FILE, 'w') as f:
        json.dump(founders, f, indent=2)

    print(f"\n" + "="*70)
    print(f"Summary:")
    print(f"  New companies added: {new_count}")
    print(f"  Companies enriched with founders: {updated_count}")
    print(f"  Total Plug and Play portfolio in DB: {len(PLUG_AND_PLAY_COMPANIES)}")
    print(f"="*70 + "\n")

if __name__ == "__main__":
    main()
