#!/usr/bin/env python3
"""
Scrape company websites for LinkedIn links from team/leadership pages.
Tries multiple common URL patterns and extracts LinkedIn profiles.
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
from pathlib import Path
import time
import re
from typing import List, Dict, Tuple

# Common team/leadership page patterns
TEAM_PAGE_PATTERNS = [
    "/team",
    "/leadership",
    "/about/team",
    "/about",
    "/company/team",
    "/people",
    "/our-team",
    "/team/",
    "/leadership/",
    "/about/",
]

def extract_linkedin_links(html: str, base_url: str) -> List[Tuple[str, str]]:
    """
    Extract LinkedIn profile links and associated names from HTML.
    Returns list of (name, linkedin_url) tuples.
    """
    soup = BeautifulSoup(html, 'html.parser')
    linkedin_matches = []
    seen_urls = set()  # Avoid duplicates

    # Find all LinkedIn profile links (only /in/, not /company/)
    for link in soup.find_all('a', href=True):
        href = link['href']
        if 'linkedin.com/in/' in href:
            # Extract profile slug
            match = re.search(r'linkedin\.com/in/([a-zA-Z0-9-]+)', href)
            if match:
                profile_slug = match.group(1)
                linkedin_url = f"https://linkedin.com/in/{profile_slug}"

                if linkedin_url in seen_urls:
                    continue
                seen_urls.add(linkedin_url)

                # Try to extract name from link text
                link_text = link.get_text(strip=True)

                if link_text and len(link_text) > 1:
                    name = link_text
                else:
                    # Try to find name in parent container
                    parent = link.find_parent(['div', 'article', 'li', 'section'])
                    if parent:
                        # Look for text nodes near the link
                        text = parent.get_text(separator=' ', strip=True)
                        # Get first few words as potential name
                        words = text.split()[:4]
                        name = ' '.join(words) if words else 'Unknown'
                    else:
                        name = 'Unknown'

                # Clean up name
                name = re.sub(r'\s+', ' ', name).strip()
                if len(name) > 100:  # Truncate overly long names
                    name = ' '.join(name.split()[:5])

                # If name is still "Unknown", try to extract from LinkedIn URL slug
                if name == 'Unknown':
                    slug_match = re.search(r'/in/([a-zA-Z0-9-]+)', linkedin_url)
                    if slug_match:
                        slug = slug_match.group(1)
                        # Convert slug to name (e.g., john-smith-123 -> john smith)
                        name = re.sub(r'-\d+$', '', slug)  # Remove trailing numbers
                        name = name.replace('-', ' ').title()

                linkedin_matches.append((name, linkedin_url))

    return linkedin_matches

def try_team_pages(company_url: str, company_name: str) -> Dict:
    """
    Try to fetch a company's team page and extract LinkedIn links.
    Returns dict with 'founders' list and 'ceo' dict.
    """
    if not company_url or company_url.strip() == '':
        return {"founders": [], "ceo": None}

    # Normalize URL
    if not company_url.startswith(('http://', 'https://')):
        company_url = 'https://' + company_url

    base_domain = urlparse(company_url).netloc

    linkedin_profiles = []

    # Try each pattern
    for pattern in TEAM_PAGE_PATTERNS:
        try:
            url = company_url.rstrip('/') + pattern
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code == 200:
                profiles = extract_linkedin_links(response.text, url)
                linkedin_profiles.extend(profiles)

                if profiles:
                    # If we found profiles, return early (good enough)
                    break
        except Exception as e:
            # Silently continue to next pattern
            continue

    # Try home page as fallback
    if not linkedin_profiles:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            response = requests.get(company_url, headers=headers, timeout=5)
            if response.status_code == 200:
                linkedin_profiles = extract_linkedin_links(response.text, company_url)
        except Exception as e:
            pass

    # Format results
    result = {"founders": [], "ceo": None}

    if linkedin_profiles:
        # Add all profiles as founders (we can't distinguish without more parsing)
        result["founders"] = [
            {"name": name, "linkedin": url}
            for name, url in linkedin_profiles
        ]

    return result

def process_batch(batch_num: int) -> int:
    """
    Process a single batch file: scrape and update founder data.
    Returns count of updated companies.
    """
    batch_file = Path(f"batches/batch_{batch_num:03d}.json")

    if not batch_file.exists():
        print(f"Batch {batch_num:03d}: File not found")
        return 0

    with open(batch_file, 'r') as f:
        batch_data = json.load(f)

    # Find companies needing updates
    to_update = [
        (name, info) for name, info in batch_data.items()
        if info.get('founders') == []
    ]

    if not to_update:
        print(f"Batch {batch_num:03d}: Already complete")
        return 0

    print(f"Batch {batch_num:03d}: Processing {len(to_update)} companies via scraping...")

    updated = 0
    for idx, (company_name, company_info) in enumerate(to_update, 1):
        url = company_info.get('url', '')
        result = try_team_pages(url, company_name)

        if result["founders"]:
            batch_data[company_name]['founders'] = result['founders']
            updated += 1

        # Print progress
        if idx % 5 == 0:
            print(f"  [{idx}/{len(to_update)}] {updated} updated so far...")

        # Save checkpoint every 10 companies
        if idx % 10 == 0:
            with open(batch_file, 'w') as f:
                json.dump(batch_data, f, indent=2)

        # Rate limiting - be gentle to servers
        time.sleep(0.3)

    # Final save
    with open(batch_file, 'w') as f:
        json.dump(batch_data, f, indent=2)

    print(f"Batch {batch_num:03d}: Complete - {updated}/{len(to_update)} companies found")
    return updated

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python3 scrape_linkedin.py START_BATCH END_BATCH")
        print("Example: python3 scrape_linkedin.py 19 21")
        sys.exit(1)

    start = int(sys.argv[1])
    end = int(sys.argv[2])

    total = 0
    for batch_num in range(start, end + 1):
        total += process_batch(batch_num)

    print(f"\n{'='*60}")
    print(f"Total companies updated across batches {start}-{end}: {total}")
