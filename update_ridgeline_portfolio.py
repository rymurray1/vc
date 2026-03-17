#!/usr/bin/env python3
"""
Update Ridgeline VC portfolio with actual verified company names.
"""

import json

FIRMS_FILE = "/Users/ryanmurray/programming/vc/firms.json"
FOUNDERS_FILE = "/Users/ryanmurray/programming/vc/founders.json"
VC_TAGS_FILE = "/Users/ryanmurray/programming/vc/vc_tags.json"

# Verified Ridgeline VC portfolio companies from agent extraction
RIDGELINE_COMPANIES = [
    "AI Squared",
    "Altana",
    "Anvl",
    "Auxon",
    "Blueshift",
    "Cape AI",
    "Cornelis Networks",
    "Composabl",
    "Eclypsium",
    "Eion",
    "Gilmour Space",
    "Harbinger",
    "Harbr",
    "Icon",
    "Implicit Cloud",
    "Agolo",
    "Knox",
    "LGND",
    "Loft Orbital",
    "Matta",
    "Machine Metrics",
    "Mesomat",
    "Multiscale",
    "Myriota",
    "Neural Magic",
    "Opentrons",
    "Planet Watchers",
    "Psionic",
    "Q-CTRL",
    "Replicated",
    "Sabi",
    "Satellite Vu",
    "Smallstep",
    "Spell",
    "StreamSets",
    "Tread",
    "Wallaroo",
    "Zenith AI",
]

def main():
    # Load files
    with open(FIRMS_FILE) as f:
        firms = json.load(f)

    with open(FOUNDERS_FILE) as f:
        founders = json.load(f)

    with open(VC_TAGS_FILE) as f:
        vc_tags = json.load(f)

    print("="*70)
    print("Updating Ridgeline VC Portfolio")
    print("="*70 + "\n")

    # Add companies to founders.json if not present
    new_count = 0
    for company_name in RIDGELINE_COMPANIES:
        if company_name not in founders:
            founders[company_name] = {
                "url": "",
                "founders": [],
                "ceo": {}
            }
            new_count += 1

    # Update Ridgeline in firms.json
    for firm in firms:
        if firm["name"] == "Ridgeline VC":
            firm["investments"] = [
                {"company": c, "url": ""} for c in RIDGELINE_COMPANIES
            ]
            print(f"Updated Ridgeline VC with {len(RIDGELINE_COMPANIES)} verified investments\n")
            break

    # Ensure vc_tags entry is correct
    vc_tags["Ridgeline VC"] = {
        "focus": ["deep tech", "infrastructure", "ai"],
        "ma_presence": False,
        "hq": "San Francisco, California",
        "website": "ridgeline.vc"
    }

    # Save files
    with open(FIRMS_FILE, 'w') as f:
        json.dump(firms, f, indent=2)

    with open(FOUNDERS_FILE, 'w') as f:
        json.dump(founders, f, indent=2)

    with open(VC_TAGS_FILE, 'w') as f:
        json.dump(vc_tags, f, indent=2)

    print(f"Added {new_count} new companies to founders.json")
    print(f"Total companies now: {len(founders)}")
    print(f"Total VCs now: {len(firms)}")
    print("\n" + "="*70)

if __name__ == "__main__":
    main()
