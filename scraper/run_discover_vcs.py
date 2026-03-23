#!/usr/bin/env python3
"""
Discover new VC firms and add them to the database.
This is Step 0 — it feeds new VCs into the system so the rest of the pipeline
(URLs → portfolios → founders → classification) can process them.

Searches DuckDuckGo for VC firms across sectors, stages, and geographies.
Extracts firm names from results and adds them to vc_tags.json + firms.json.

Usage:
    python run_discover_vcs.py                # Run all discovery queries
    python run_discover_vcs.py --limit 10     # Only run 10 queries
    python run_discover_vcs.py --dry-run      # Preview without saving
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.vc_discovery import VCDiscovery


def main():
    parser = argparse.ArgumentParser(description="Discover new VC firms")
    parser.add_argument("--limit", type=int, default=None, help="Max queries to run")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    disc = VCDiscovery()
    existing = disc.get_existing_firms()

    print(f"\nVC Discovery")
    print(f"{'=' * 60}")
    print(f"Existing firms in database: {len(existing)}")
    print(f"Discovery queries:          {55 if not args.limit else args.limit}")
    print(f"Dry run:                    {args.dry_run}")
    print(f"{'=' * 60}\n")

    result = disc.discover(limit=args.limit, dry_run=args.dry_run)

    print(f"\n{'=' * 60}")
    print(f"Done.")
    print(f"  New VCs discovered:  {result['new_vcs_found']}")
    print(f"  Already in database: {result['already_known']}")
    print()

    if result.get("new_firms"):
        print(f"New firms added:")
        for name in result["new_firms"][:30]:
            print(f"  + {name}")
        if len(result["new_firms"]) > 30:
            print(f"  ... and {len(result['new_firms']) - 30} more")

    if not args.dry_run and result["new_vcs_found"] > 0:
        print(f"\nSaved to vc_tags.json and firms.json")
        print(f"Run the full pipeline next to fill in their data:")
        print(f"  python scraper/run_all.py")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
