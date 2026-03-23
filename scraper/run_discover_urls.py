#!/usr/bin/env python3
"""
Discover website URLs for VC firms that don't have them.
Searches DuckDuckGo for each firm and saves the best URL to vc_tags.json.

Usage:
    python run_discover_urls.py                # Run on all firms missing URLs
    python run_discover_urls.py --limit 20     # Only process 20 firms
    python run_discover_urls.py --dry-run      # Preview without saving
"""

import sys
import os
import argparse
import logging

# Add project root to path so scraper module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.url_discovery import URLDiscovery


def main():
    parser = argparse.ArgumentParser(description="Discover VC firm website URLs")
    parser.add_argument("--limit", type=int, default=None, help="Max firms to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    disc = URLDiscovery()
    missing = disc.get_firms_without_urls()

    print(f"\nVC URL Discovery")
    print(f"{'=' * 60}")
    print(f"Firms missing URLs: {len(missing)}")
    if args.limit:
        print(f"Processing limit:   {args.limit}")
    print(f"Dry run:            {args.dry_run}")
    print(f"{'=' * 60}\n")

    result = disc.discover_batch(limit=args.limit, dry_run=args.dry_run)

    print(f"\n{'=' * 60}")
    print(f"Done. Found {result['found']} / {result['total']} URLs")
    if not args.dry_run and result["found"] > 0:
        print(f"Saved to vc_tags.json")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
