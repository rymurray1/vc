#!/usr/bin/env python3
import json
import os
from pathlib import Path
from anthropic import Anthropic

# Initialize Anthropic client
client = Anthropic()

BATCHES_DIR = Path("batches")
BATCH_FILES = sorted(BATCHES_DIR.glob("batch_*.json"))

def search_founder_info(company_name: str, url: str = "") -> dict:
    """Search for founder and CEO info via Claude's web search."""
    query = f"{company_name} founder CEO LinkedIn"

    # Use Claude with web search to find info
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": f"Search for founder and CEO information for {company_name}. Return ONLY valid JSON with keys: 'founders' (list of {{'name': '', 'linkedin': ''}}), 'ceo' ({{'name': '', 'linkedin': ''}}), or null if not found. Be concise."
            }
        ]
    )

    try:
        result = json.loads(message.content[0].text)
        return result
    except (json.JSONDecodeError, IndexError):
        return {"founders": [], "ceo": None}

def process_batch(batch_file: Path, batch_num: int):
    """Process a single batch file and update founders/CEO data."""
    with open(batch_file, 'r') as f:
        batch_data = json.load(f)

    updated_count = 0
    companies_to_update = []

    # Find companies with empty founders
    for company_name, company_info in batch_data.items():
        if company_info.get('founders') == []:
            companies_to_update.append(company_name)

    print(f"Batch {batch_num}: Found {len(companies_to_update)} companies to update")

    # Process in groups
    for i, company_name in enumerate(companies_to_update):
        print(f"  [{i+1}/{len(companies_to_update)}] Searching {company_name}...", end=" ", flush=True)

        url = batch_data[company_name].get('url', '')
        founder_info = search_founder_info(company_name, url)

        if founder_info.get('founders') or founder_info.get('ceo'):
            batch_data[company_name]['founders'] = founder_info.get('founders', [])
            batch_data[company_name]['ceo'] = founder_info.get('ceo', None)
            updated_count += 1
            print("✓ Updated")
        else:
            print("✗ Skipped (not found)")

        # Save progress every 5 companies
        if (i + 1) % 5 == 0:
            with open(batch_file, 'w') as f:
                json.dump(batch_data, f, indent=2)
            print(f"    [Progress saved: {updated_count} updated]")

    # Final save
    with open(batch_file, 'w') as f:
        json.dump(batch_data, f, indent=2)

    print(f"  Batch {batch_num} complete: {updated_count} companies updated\n")
    return updated_count

def main():
    print(f"Found {len(BATCH_FILES)} batch files")
    print(f"Processing batches in parallel via API calls...\n")

    total_updated = 0
    for i, batch_file in enumerate(BATCH_FILES[:3], 1):  # Start with first 3 as test
        batch_num = int(batch_file.stem.split('_')[1])
        updated = process_batch(batch_file, batch_num)
        total_updated += updated

    print(f"\nTotal companies updated: {total_updated}")

if __name__ == "__main__":
    main()
