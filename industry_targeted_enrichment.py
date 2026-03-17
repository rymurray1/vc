#!/usr/bin/env python3
"""
Industry-targeted founder enrichment.
Groups companies by likely industry and uses industry-specific search patterns.
"""

import json
import os
import requests
import time
import re

FOUNDERS_FILE = "/Users/ryanmurray/programming/vc/founders.json"
ENV_FILE = "/Users/ryanmurray/programming/vc/enricher/.env"

def load_api_key():
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

def extract_founder_info(text):
    """Extract founder names and LinkedIn URLs."""
    linkedin_pattern = r'https://linkedin\.com/in/[a-zA-Z0-9\-]+'
    linkedin_urls = re.findall(linkedin_pattern, text)
    return linkedin_urls

def infer_industry(company_name):
    """Infer industry from company name keywords."""
    name_lower = company_name.lower()

    industries = {
        "biotech": ["bio", "therapeutics", "genomics", "pharma", "vaccine", "crispr", "gene"],
        "fintech": ["pay", "bank", "finance", "crypto", "blockchain", "lending", "invest", "trading"],
        "energy": ["energy", "power", "solar", "wind", "battery", "fuel", "grid", "electric"],
        "health": ["health", "medical", "clinic", "doctor", "therapy", "care", "pharma"],
        "ai": ["ai", "machine learning", "neural", "algorithm", "model", "intelligence"],
        "hardware": ["semiconductor", "chip", "processor", "device", "hardware", "robotics"],
        "saas": ["software", "saas", "platform", "analytics", "tools", "management"],
        "ecommerce": ["shop", "store", "commerce", "retail", "marketplace", "mall"],
    }

    for industry, keywords in industries.items():
        if any(keyword in name_lower for keyword in keywords):
            return industry

    return "general"

def enrich_with_industry_queries(company_name, industry, api_key):
    """Use industry-specific queries to find founders."""
    queries = {
        "biotech": [
            f"{company_name} founder scientist",
            f"{company_name} phd founder",
            f"{company_name} chief scientific officer",
        ],
        "fintech": [
            f"{company_name} founders fintech",
            f"{company_name} ceo cto founders",
            f"{company_name} banking founders",
        ],
        "energy": [
            f"{company_name} clean energy founder",
            f"{company_name} sustainable founder",
            f"{company_name} energy startup founder",
        ],
        "ai": [
            f"{company_name} ai researcher founder",
            f"{company_name} ml engineer founder",
            f"{company_name} phd ai founder",
        ],
    }

    selected_queries = queries.get(industry, [
        f"{company_name} founder",
        f"{company_name} founder ceo",
        f'"{company_name}" startup founder',
    ])

    all_founders = []
    seen = set()

    for query in selected_queries:
        result = serper_search(query, api_key)
        if result and "organic" in result:
            for item in result["organic"][:3]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")

                # Extract names from title
                # Common patterns: "Name is the founder of Company"
                matches = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', title)
                for match in matches:
                    if match.lower() not in seen and len(match) < 50:
                        all_founders.append({"name": match, "linkedin": ""})
                        seen.add(match.lower())

                # Extract LinkedIn URLs
                linkedin_urls = extract_founder_info(title + " " + snippet)
                for url in linkedin_urls:
                    all_founders.append({
                        "name": url.split("/in/")[-1].replace("-", " ").title(),
                        "linkedin": url
                    })

        time.sleep(0.2)

    return all_founders[:3]

def main():
    api_key = load_api_key()
    if not api_key:
        print("ERROR: API key not found")
        return

    with open(FOUNDERS_FILE) as f:
        founders = json.load(f)

    empty = [(k, v) for k, v in founders.items() if not v.get("founders")]

    print(f"\n{'='*70}")
    print(f"Industry-Targeted Founder Enrichment")
    print(f"{'='*70}")
    print(f"Companies to enrich: {len(empty)}\n")

    updated = 0

    for i, (company_name, _) in enumerate(empty, 1):
        industry = infer_industry(company_name)
        print(f"[{i}/{len(empty)}] {company_name} ({industry})...", end=" ", flush=True)

        founder_list = enrich_with_industry_queries(company_name, industry, api_key)

        if founder_list:
            founders[company_name]["founders"] = founder_list
            founders[company_name]["ceo"] = founder_list[0]
            updated += 1
            print(f"✓ {founder_list[0]['name']}")

            with open(FOUNDERS_FILE, "w") as f:
                json.dump(founders, f, indent=2)
        else:
            print("✗")

        time.sleep(0.3)

    print(f"\n{'='*70}")
    print(f"Updated: {updated}")
    print(f"Total: {sum(1 for v in founders.values() if v.get('founders'))}/{len(founders)}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
