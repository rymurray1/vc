#!/usr/bin/env python3
"""
Enrich founders.json with founder info using Serper API.
Searches for companies with empty founders list and finds their founder/cofounder details.

Usage:
  python3 enrich_founders_serper.py              # Process all incomplete companies
  python3 enrich_founders_serper.py --dry-run    # Preview without updating
  python3 enrich_founders_serper.py --limit 50   # Process only 50 companies
"""

import json
import os
import sys
import requests
import time
import re
from pathlib import Path

FOUNDERS_FILE = "/Users/ryanmurray/programming/vc/founders.json"
ENV_FILE = "/Users/ryanmurray/programming/vc/enricher/.env"

def load_api_key():
    """Load Serper API key from .env file."""
    if not os.path.exists(ENV_FILE):
        print(f"ERROR: {ENV_FILE} not found")
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

def extract_names_from_text(text):
    """Extract names (capitalized words) from text."""
    # Look for patterns like "Name is the founder" or just capitalized names
    words = text.split()
    names = []
    for i, word in enumerate(words):
        # Look for capitalized words that might be names
        if word[0].isupper() and len(word) > 2 and word not in ['The', 'A', 'And', 'Co', 'Inc', 'CEO', 'Founded']:
            # Check if next word is also capitalized (typical name pattern)
            if i + 1 < len(words) and words[i+1][0].isupper() and len(words[i+1]) > 2:
                name = f"{word} {words[i+1]}"
                if name not in names and len(name) > 5:
                    names.append(name)
    return names

def parse_serper_for_founders(company_name, serper_data):
    """Extract founder/cofounder info from Serper results."""
    founders = []
    ceo = {}

    if not serper_data or "organic" not in serper_data:
        return {"founders": founders, "ceo": ceo}

    all_linkedin_urls = {}
    all_founder_names = set()

    # Process top 5 results
    for result in serper_data.get("organic", [])[:5]:
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        url = result.get("link", "")

        combined_text = title + " " + snippet

        # Extract LinkedIn URLs and map them
        linkedin_urls = extract_linkedin_urls(combined_text)
        for linkedin_url in linkedin_urls:
            profile_slug = linkedin_url.split("/in/")[-1].rstrip("/")
            all_linkedin_urls[profile_slug.lower()] = linkedin_url

        # Look for founder/cofounder mentions
        lower_text = combined_text.lower()
        if "founder" in lower_text or "cofounder" in lower_text or "co-founder" in lower_text:
            # Extract capitalized names
            names = extract_names_from_text(combined_text)
            all_founder_names.update(names)

    # Build founders list
    for name in sorted(all_founder_names):
        # Try to find matching LinkedIn URL
        name_slug = name.lower().replace(" ", "-")
        linkedin_url = ""

        # Exact or partial match
        for slug, url in all_linkedin_urls.items():
            if name_slug in slug or slug in name_slug:
                linkedin_url = url
                break

        founders.append({
            "name": name,
            "linkedin": linkedin_url
        })

    # Set CEO as first founder if available
    if founders:
        ceo = founders[0]

    return {"founders": founders, "ceo": ceo}

def main():
    api_key = load_api_key()
    if not api_key:
        print("ERROR: Serper API key not found")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    limit = None

    # Parse --limit argument
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            try:
                limit = int(sys.argv[idx + 1])
            except ValueError:
                pass

    # Load founders.json
    with open(FOUNDERS_FILE) as f:
        founders_data = json.load(f)

    # Find companies with empty founders
    incomplete = [(k, v) for k, v in founders_data.items() if not v.get("founders")]
    print(f"\nTotal companies: {len(founders_data)}")
    print(f"Companies with empty founders: {len(incomplete)}")

    if limit:
        incomplete = incomplete[:limit]
        print(f"Processing (limited to): {len(incomplete)}")

    print(f"Dry-run: {dry_run}")
    print(f"\n{'='*60}\n")

    updated_count = 0

    for i, (company_name, company_info) in enumerate(incomplete, 1):
        print(f"[{i}/{len(incomplete)}] {company_name}...", end=" ", flush=True)

        # Search for founder info
        query = f"{company_name} founder cofounder linkedin"
        serper_data = serper_search(query, api_key)

        if serper_data:
            founder_info = parse_serper_for_founders(company_name, serper_data)

            if founder_info["founders"]:
                if not dry_run:
                    founders_data[company_name]["founders"] = founder_info["founders"]
                    founders_data[company_name]["ceo"] = founder_info["ceo"]
                    updated_count += 1

                founder_names = ", ".join(f["name"] for f in founder_info["founders"][:2])
                print(f"✓ {founder_names}")

                # Save after each company
                if not dry_run:
                    with open(FOUNDERS_FILE, "w") as f:
                        json.dump(founders_data, f, indent=2)
            else:
                print("✗ Not found")
        else:
            print("✗ API error")

        # Respectful delay
        time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"Total companies updated: {updated_count}")
    if not dry_run:
        print(f"Saved to {FOUNDERS_FILE}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
