#!/usr/bin/env python3
"""
Multi-strategy founder enrichment using Serper API.
Tries multiple search queries per company for better results.
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
    payload = {"q": query, "num": 10}

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

def extract_names_and_urls(serper_data):
    """Extract founder names and LinkedIn URLs from Serper results."""
    names = set()
    linkedin_urls = {}

    if not serper_data or "organic" not in serper_data:
        return names, linkedin_urls

    for result in serper_data.get("organic", [])[:5]:
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        combined = title + " " + snippet

        # Extract LinkedIn URLs
        urls = extract_linkedin_urls(combined)
        for url in urls:
            slug = url.split("/in/")[-1].rstrip("/").lower()
            linkedin_urls[slug] = url

        # Extract potential founder names (capitalized words)
        words = combined.split()
        for i, word in enumerate(words):
            if (word[0].isupper() and len(word) > 2 and
                i + 1 < len(words) and words[i+1][0].isupper()):
                potential_name = f"{word} {words[i+1]}"
                if len(potential_name) < 50 and "linkedin" not in potential_name.lower():
                    names.add(potential_name)

    return names, linkedin_urls

def enrich_company(company_name, api_key):
    """Try multiple search strategies to find founder info."""
    # Strategy 1: Direct founder search
    queries = [
        f"{company_name} founder CEO",
        f"{company_name} co-founder",
        f'"{company_name}" founder linkedin',
        f"{company_name} founders team",
        f"{company_name} startup founder",
    ]

    all_names = set()
    all_linkedin = {}

    for query in queries:
        result = serper_search(query, api_key)
        if result:
            names, linkedin_urls = extract_names_and_urls(result)
            all_names.update(names)
            all_linkedin.update(linkedin_urls)
            time.sleep(0.2)  # Small delay between queries

    # Build founder list
    founders = []
    for name in sorted(all_names):
        name = name.strip()
        if len(name) > 3:
            # Try to find matching LinkedIn
            name_slug = name.lower().replace(" ", "-")
            linkedin_url = ""

            for slug, url in all_linkedin.items():
                if name_slug in slug or slug in name_slug:
                    linkedin_url = url
                    break

            founders.append({
                "name": name,
                "linkedin": linkedin_url
            })

    return {
        "founders": founders[:3],  # Cap at 3 founders
        "ceo": founders[0] if founders else {}
    }

def main():
    api_key = load_api_key()
    if not api_key:
        print("ERROR: Serper API key not found")
        return

    # Load founders.json
    with open(FOUNDERS_FILE) as f:
        founders = json.load(f)

    # Find empty companies
    empty_companies = [(k, v) for k, v in founders.items() if not v.get("founders")]

    print(f"\n{'='*70}")
    print(f"Multi-Strategy Founder Enrichment")
    print(f"{'='*70}")
    print(f"Companies to enrich: {len(empty_companies)}\n")

    updated_count = 0

    for i, (company_name, company_info) in enumerate(empty_companies, 1):
        print(f"[{i}/{len(empty_companies)}] {company_name}...", end=" ", flush=True)

        founder_info = enrich_company(company_name, api_key)

        if founder_info["founders"]:
            founders[company_name]["founders"] = founder_info["founders"]
            founders[company_name]["ceo"] = founder_info["ceo"]
            updated_count += 1

            names = ", ".join(f["name"] for f in founder_info["founders"][:2])
            print(f"✓ {names}")

            # Save after each company for checkpointing
            with open(FOUNDERS_FILE, "w") as f:
                json.dump(founders, f, indent=2)
        else:
            print("✗ Not found")

        time.sleep(0.3)

    print(f"\n{'='*70}")
    print(f"Updated: {updated_count} companies")
    print(f"Total with founders now: {sum(1 for v in founders.values() if v.get('founders'))}/{len(founders)}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
