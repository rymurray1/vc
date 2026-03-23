#!/usr/bin/env python3
"""
Enrich companies in founders.json with founder/CEO names and LinkedIn URLs.
Uses the internal DDG search scraper (no API key needed).

Usage:
    python run_enrich.py                # Run on all unenriched companies
    python run_enrich.py --limit 50     # Only process 50 companies
    python run_enrich.py --dry-run      # Preview without saving
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.enrichment import EnrichmentEngine


def main():
    parser = argparse.ArgumentParser(description="Enrich founder/CEO data")
    parser.add_argument("--limit", type=int, default=None, help="Max companies to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    engine = EnrichmentEngine()
    stats = engine.get_coverage_stats()
    incomplete = engine.get_incomplete_companies()

    print(f"\nFounder/CEO Enrichment")
    print(f"{'=' * 60}")
    print(f"Total companies:    {stats['total_companies']}")
    print(f"Already enriched:   {stats['enriched']}")
    print(f"Needing enrichment: {stats['empty']}")
    print(f"Coverage:           {stats['coverage_pct']}%")
    if args.limit:
        print(f"Processing limit:   {args.limit}")
    print(f"Dry run:            {args.dry_run}")
    print(f"{'=' * 60}\n")

    result = engine.enrich_batch(limit=args.limit, dry_run=args.dry_run)

    print(f"\n{'=' * 60}")
    print(f"Done.")
    print(f"  Companies enriched: {result['enriched']}")
    print(f"  Not found:          {result['failed']}")
    if not args.dry_run and result["enriched"] > 0:
        print(f"\nSaved to founders.json")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
