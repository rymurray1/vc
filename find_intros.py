#!/usr/bin/env python3

import json
import csv
import sys
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

def extract_linkedin_slug(url):
    """Extract LinkedIn slug from URL, normalized."""
    if not url or not isinstance(url, str):
        return None

    # Remove trailing slashes and whitespace
    url = url.strip().rstrip('/')

    # Extract the slug (last part of the path)
    # Handle both linkedin.com/in/slug and www.linkedin.com/in/slug
    if '/in/' in url:
        slug = url.split('/in/')[-1]
        # Remove any query params or fragments
        slug = slug.split('?')[0].split('#')[0].strip('/')
        return slug.lower()

    return None

def fuzzy_match_firm(target_name, firm_list, threshold=0.6):
    """Fuzzy match a firm name against the list of firms."""
    best_match = None
    best_score = threshold

    for firm in firm_list:
        score = SequenceMatcher(None, target_name.lower(), firm['name'].lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = firm

    return best_match

def load_connections(csv_path):
    """Load LinkedIn connections from CSV, extract slugs."""
    connections = {}

    if not Path(csv_path).exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slug = extract_linkedin_slug(row.get('Linkedin URL', ''))
            if slug:
                connections[slug] = {
                    'name': row.get('Name', ''),
                    'title': row.get('Title', ''),
                    'company': '',  # We won't know their company from the export
                }

    return connections

def list_firms(firms_path):
    """Print list of all available VC firms."""
    with open(firms_path, 'r', encoding='utf-8') as f:
        firms = json.load(f)

    print(f"Available VC firms ({len(firms)}):")
    for i, firm in enumerate(firms, 1):
        inv_count = len(firm.get('investments', []))
        print(f"  {i}. {firm['name']} ({inv_count} investments)")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 find_intros.py --list-firms")
        print("  python3 find_intros.py <VC_FIRM_NAME> <linkedin_connections.csv>")
        sys.exit(1)

    if sys.argv[1] == '--list-firms':
        list_firms('firms.json')
        return

    if len(sys.argv) < 3:
        print("Error: Must provide both VC firm name and CSV path")
        print("Usage: python3 find_intros.py <VC_FIRM_NAME> <linkedin_connections.csv>")
        sys.exit(1)

    target_vc = sys.argv[1]
    csv_path = sys.argv[2]

    # Load all data
    print(f"Loading data...")
    with open('firms.json', 'r', encoding='utf-8') as f:
        firms = json.load(f)

    with open('founders.json', 'r', encoding='utf-8') as f:
        founders_db = json.load(f)

    connections = load_connections(csv_path)
    print(f"Loaded {len(connections)} LinkedIn connections")

    # Find matching VC firm
    matched_firm = fuzzy_match_firm(target_vc, firms)
    if not matched_firm:
        print(f"Error: Could not find VC firm matching '{target_vc}'")
        print("Use --list-firms to see available options")
        sys.exit(1)

    print(f"Found VC: {matched_firm['name']}")

    # Get portfolio companies
    portfolio_companies = [inv['company'] for inv in matched_firm.get('investments', [])]
    print(f"Portfolio: {len(portfolio_companies)} companies")

    # Find founders in our connections
    results = []

    for company_name in portfolio_companies:
        if company_name not in founders_db:
            continue

        company_data = founders_db[company_name]

        # Check founders
        for founder in company_data.get('founders', []):
            slug = extract_linkedin_slug(founder.get('linkedin', ''))
            if slug and slug in connections:
                results.append({
                    'vc_firm': matched_firm['name'],
                    'portfolio_company': company_name,
                    'person_role': 'Founder',
                    'person_name': founder.get('name', ''),
                    'person_linkedin': founder.get('linkedin', ''),
                    'connection_name': connections[slug]['name'],
                    'connection_title': connections[slug]['title'],
                    'connection_company': connections[slug]['company'],
                })

        # Check CEO
        ceo = company_data.get('ceo')
        if ceo:
            slug = extract_linkedin_slug(ceo.get('linkedin', ''))
            if slug and slug in connections:
                results.append({
                    'vc_firm': matched_firm['name'],
                    'portfolio_company': company_name,
                    'person_role': 'CEO',
                    'person_name': ceo.get('name', ''),
                    'person_linkedin': ceo.get('linkedin', ''),
                    'connection_name': connections[slug]['name'],
                    'connection_title': connections[slug]['title'],
                    'connection_company': connections[slug]['company'],
                })

    # Write results
    if results:
        output_path = 'intro_results.csv'
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'vc_firm', 'portfolio_company', 'person_role', 'person_name',
                'person_linkedin', 'connection_name', 'connection_title', 'connection_company'
            ])
            writer.writeheader()
            writer.writerows(results)

        print(f"\nFound {len(results)} intro paths to {matched_firm['name']}:")
        for r in results:
            print(f"  → {r['person_name']} ({r['person_role']} @ {r['portfolio_company']}) — connected to {r['connection_name']}")

        print(f"\nResults saved to {output_path}")
    else:
        print(f"\nNo intro paths found to {matched_firm['name']}")

if __name__ == '__main__':
    main()
