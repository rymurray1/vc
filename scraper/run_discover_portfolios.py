#!/usr/bin/env python3
"""
Discover portfolio companies for VC firms with empty investment lists.
Uses DDG search + direct portfolio page scraping.

Saves to firms.json and adds new companies to founders.json.

Usage:
    python run_discover_portfolios.py                # Run on all empty firms
    python run_discover_portfolios.py --limit 20     # Only process 20 firms
    python run_discover_portfolios.py --dry-run      # Preview without saving
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.portfolio_scraper import PortfolioScraper


def main():
    parser = argparse.ArgumentParser(description="Discover VC portfolio companies")
    parser.add_argument("--limit", type=int, default=None, help="Max firms to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    scraper = PortfolioScraper()
    empty = scraper.get_empty_firms()

    print(f"\nVC Portfolio Discovery")
    print(f"{'=' * 60}")
    print(f"Firms with empty portfolios: {len(empty)}")
    if args.limit:
        print(f"Processing limit:           {args.limit}")
    print(f"Dry run:                    {args.dry_run}")
    print(f"{'=' * 60}\n")

    result = scraper.discover_batch(limit=args.limit, dry_run=args.dry_run)

    print(f"\n{'=' * 60}")
    print(f"Done.")
    print(f"  Firms with companies found: {result['found']}")
    print(f"  Firms with nothing found:   {result['skipped']}")
    print()

    if result.get("results"):
        print(f"Companies discovered:")
        for r in result["results"]:
            sample = ", ".join(r["sample"])
            print(f"  {r['firm']:40s} {r['count']:3d} companies  ({sample}...)")

    if not args.dry_run and result["found"] > 0:
        print(f"\nSaved to firms.json and founders.json")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
