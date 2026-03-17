#!/usr/bin/env python3
"""
Use Serper API to find founder and cofounder information.
Searches for company founders/cofounders and extracts names + LinkedIn profiles.

Usage:
  python3 find_founders_serper.py              # Process all incomplete batches
  python3 find_founders_serper.py [batch_num]  # Process specific batch
  python3 find_founders_serper.py --dry-run    # Preview without updating
"""

import json
import os
import sys
import requests
import time
from pathlib import Path

BATCHES_DIR = Path("batches")
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
        print(f"  ERROR: Serper search failed: {e}")
        return None

def extract_linkedin_urls(text):
    """Extract LinkedIn profile URLs from text."""
    import re
    linkedin_pattern = r'https://linkedin\.com/in/[a-zA-Z0-9\-]+'
    return re.findall(linkedin_pattern, text)

def parse_founder_info(company_name, serper_data):
    """Parse Serper results to extract founder/cofounder names and LinkedIn profiles."""
    founders = []
    ceo = {}

    if not serper_data or "organic" not in serper_data:
        return {"founders": founders, "ceo": ceo}

    all_names = set()
    all_linkedin = {}

    # Search through organic results for founder info
    for result in serper_data.get("organic", [])[:5]:
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        url = result.get("link", "")

        # Extract LinkedIn URLs
        linkedin_urls = extract_linkedin_urls(title + " " + snippet + " " + url)
        for linkedin_url in linkedin_urls:
            # Extract name from LinkedIn URL or title
            profile_slug = linkedin_url.split("/in/")[-1].rstrip("/")
            all_linkedin[profile_slug] = linkedin_url

        # Look for founder/cofounder names in title and snippet
        combined_text = (title + " " + snippet).lower()

        # Pattern: "Name is the founder/cofounder of Company"
        import re
        founder_patterns = [
            r"([A-Z][a-z]+ [A-Z][a-z]+).*(?:founder|cofounder|co-founder)",
            r"(?:founder|cofounder|co-founder).*?([A-Z][a-z]+ [A-Z][a-z]+)",
            r"([A-Z][a-z]+ [A-Z][a-z]+).*?(?:founder|cofounder|co-founder|ceo|chief executive)",
        ]

        for pattern in founder_patterns:
            matches = re.finditer(pattern, title + " " + snippet)
            for match in matches:
                name = match.group(1).strip()
                if len(name) > 3:
                    all_names.add(name)

    # Build founders list with LinkedIn URLs if available
    for name in sorted(all_names):
        # Try to find LinkedIn URL for this name
        name_slug = name.lower().replace(" ", "-")
        linkedin_url = ""

        # Check if we have exact match
        for slug, url in all_linkedin.items():
            if name_slug in slug or slug in name_slug:
                linkedin_url = url
                break

        founders.append({
            "name": name,
            "linkedin": linkedin_url
        })

    # Try to identify CEO
    if founders:
        ceo = founders[0]  # First founder/cofounder as CEO

    return {"founders": founders, "ceo": ceo}

def process_batch(batch_num, api_key, dry_run=False):
    """Process a single batch file."""
    batch_file = BATCHES_DIR / f"batch_{batch_num:03d}.json"

    if not batch_file.exists():
        print(f"Batch {batch_num}: File not found")
        return 0

    with open(batch_file) as f:
        batch_data = json.load(f)

    updated_count = 0
    total_companies = len(batch_data)

    print(f"\nBatch {batch_num}: Processing {total_companies} companies")

    for i, (company_name, company_info) in enumerate(batch_data.items(), 1):
        # Skip if already has founders
        if company_info.get("founders"):
            continue

        print(f"  [{i}/{total_companies}] {company_name}...", end=" ", flush=True)

        # Search for founder info
        query = f"{company_name} founder cofounder linkedin"
        serper_data = serper_search(query, api_key)

        if serper_data:
            founder_info = parse_founder_info(company_name, serper_data)

            if founder_info["founders"] or founder_info["ceo"]:
                if not dry_run:
                    batch_data[company_name]["founders"] = founder_info["founders"]
                    batch_data[company_name]["ceo"] = founder_info["ceo"]
                    updated_count += 1

                founder_names = ", ".join(f["name"] for f in founder_info["founders"][:2])
                print(f"✓ Found: {founder_names}")
            else:
                print("✗ Not found")
        else:
            print("✗ API error")

        # Save progress every 10 companies
        if (i % 10 == 0) and not dry_run:
            with open(batch_file, "w") as f:
                json.dump(batch_data, f, indent=2)
            print(f"    [Saved progress: {updated_count} updated]")

        # Small delay to be respectful
        time.sleep(0.5)

    # Final save
    if not dry_run:
        with open(batch_file, "w") as f:
            json.dump(batch_data, f, indent=2)

    print(f"  Batch {batch_num} complete: {updated_count} companies updated")
    return updated_count

def main():
    api_key = load_api_key()
    if not api_key:
        print("ERROR: Serper API key not found")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv

    # Determine which batches to process
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        batch_num = int(sys.argv[1])
        batches = [batch_num]
    else:
        # Process all batches
        batch_files = sorted(BATCHES_DIR.glob("batch_*.json"))
        batches = [int(f.stem.split("_")[1]) for f in batch_files]

    print(f"{'='*60}")
    print(f"Founder Lookup via Serper API")
    print(f"{'='*60}")
    print(f"Dry-run: {dry_run}")
    print(f"Processing {len(batches)} batches")

    total_updated = 0
    for batch_num in batches:
        updated = process_batch(batch_num, api_key, dry_run=dry_run)
        total_updated += updated

    print(f"\n{'='*60}")
    print(f"Total companies updated: {total_updated}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
