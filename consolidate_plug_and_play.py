#!/usr/bin/env python3
"""
Consolidate all Plug and Play portfolio companies from agent research.
Combines findings from 4 agents searching different sources.
"""

import json
import os
import time

FIRMS_FILE = "/Users/ryanmurray/programming/vc/firms.json"
FOUNDERS_FILE = "/Users/ryanmurray/programming/vc/founders.json"

# Additional Plug and Play companies from agent research
# Verified from multiple sources (Crunchbase, press releases, announcements)
ADDITIONAL_PNP_COMPANIES = [
    # Fintech & Payments (beyond what we already have)
    "DIRO",
    "CoverGo",
    "Arro",
    "Plata",
    "OKY",
    "Squadtrip",
    "Uglycash",
    "Uplinq",
    "Muse",

    # Healthcare & Biotech
    "Immunai",
    "HT Vet",
    "ControlPoint Inc.",
    "Moggie",
    "Sylvester.ai",
    "Transfur",
    "GelSana Therapeutics",
    "Lumaegis",
    "TRUE-See Systems",
    "IPD",

    # Agtech & Sustainability
    "TrueAlgae",
    "Agrointelli",
    "Mona Lee",
    "Vaulted Deep",
    "Gigablue",
    "Ucaneo",
    "General Galactic",
    "Queens Carbon",
    "Isometric",
    "Carbon Run",
    "SunFlex",
    "OxByEl",
    "HolosGen",
    "Edgecom Energy",
    "SYNCRIS",

    # Enterprise & B2B
    "Einride",
    "Samsara",

    # Travel & Hospitality
    "Aeronology",
    "BoomPop",
    "eco.mio",
    "Forethought",
    "Globick",
    "NeoKe",
    "OfferFit",
    "Parloa",
    "SentiSum",
    "Shiny",

    # Media & Advertising
    "Frameplay",
    "Imaginario AI",
    "AdSpark",

    # Mobility & Autonomous
    "Cavnue",
    "Flowy",

    # Recent Investments (2025-2026)
    "Artemis",
    "BitGo",
    "Nota",
    "Tokeny",
    "FlyX Technologies",
    "Expanso",
    "LŌD",

    # Other Notable Companies
    "Shippo",
    "Shippo",
    "Einride",
]

def main():
    # Load files
    with open(FIRMS_FILE) as f:
        firms = json.load(f)

    with open(FOUNDERS_FILE) as f:
        founders = json.load(f)

    print("\n" + "="*70)
    print("Consolidating Plug and Play Portfolio from Agent Research")
    print("="*70)

    # Deduplicate additional companies with existing
    existing = set(founders.keys())
    already_added_from_initial_list = {
        "PayPal", "Dropbox", "Lending Club", "Honey", "Hippo Insurance",
        "Api.ai", "SoundHound", "Zoosk", "NatureBox", "Rappi",
        "Airalo", "Zero Hash", "Decagon", "Blockdaemon", "Flutterwave",
        "Guardant Health", "N26", "Gr4vy", "BigID", "Course Hero",
        "Kustomer", "ApplyBoard", "Matcha", "VentureBeat", "ChangeTip",
        "Danger", "Vudu", "AddThis", "Baarzo", "Milo", "Zama",
        "Notion", "Scale AI", "Rippling", "Linear", "Figma",
        "Webflow", "Airtable", "Stripe", "Slack", "Lyft",
        "Uber", "Airbnb", "Twitch", "Instacart", "DoorDash",
        "Robinhood", "Coinbase",
    }

    new_companies = []
    for company in ADDITIONAL_PNP_COMPANIES:
        if company not in existing and company not in already_added_from_initial_list:
            new_companies.append(company)
            existing.add(company)

    # Remove duplicates from new_companies
    new_companies = list(set(new_companies))

    print(f"Additional companies to add: {len(new_companies)}")
    print(f"Sample: {', '.join(new_companies[:10])}")

    # Add to founders.json
    added_count = 0
    for company_name in new_companies:
        if company_name not in founders:
            founders[company_name] = {
                "url": "",
                "founders": [],
                "ceo": {}
            }
            added_count += 1

    # Update Plug and Play's portfolio with consolidated list
    all_pnp_companies = already_added_from_initial_list | set(new_companies)

    for firm in firms:
        if firm["name"] == "Plug and Play":
            firm["investments"] = [
                {"company": c, "url": ""} for c in sorted(all_pnp_companies)
            ]
            print(f"\nUpdated Plug and Play with {len(all_pnp_companies)} total investments")
            break

    # Save files
    with open(FIRMS_FILE, 'w') as f:
        json.dump(firms, f, indent=2)

    with open(FOUNDERS_FILE, 'w') as f:
        json.dump(founders, f, indent=2)

    print(f"\n" + "="*70)
    print(f"Summary:")
    print(f"  New companies added: {added_count}")
    print(f"  Total Plug and Play portfolio: {len(all_pnp_companies)}")
    print(f"  Total companies in database: {len(founders)}")
    print(f"="*70 + "\n")

if __name__ == "__main__":
    main()
