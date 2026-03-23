#!/usr/bin/env python3
"""
Run the full VC data pipeline:
  Step 0: Discover new VC firms (searches for VCs across sectors/geographies)
  Step 1: Discover website URLs for firms missing them
  Step 2: Discover portfolio companies for firms with empty portfolios
  Step 3: Enrich companies with founder/CEO data + LinkedIn URLs
  Step 4: Classify VCs by sector, stage, and geography

Each step saves progress as it goes, so you can kill and restart safely.

Usage:
    python run_all.py                    # Run everything (steps 0-4)
    python run_all.py --limit 20         # Process 20 items per step
    python run_all.py --dry-run          # Preview all steps without saving
    python run_all.py --step 0           # Run only step 0 (discover VCs)
    python run_all.py --step 2           # Run only step 2 (portfolios)
"""

import sys
import os
import argparse
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.vc_discovery import VCDiscovery
from scraper.url_discovery import URLDiscovery
from scraper.portfolio_scraper import PortfolioScraper
from scraper.enrichment import EnrichmentEngine
from scraper.vc_classifier import VCClassifier


def step0_discover_vcs(limit, dry_run):
    """Search for new VC firms and add them to the database."""
    print("\n" + "=" * 60)
    print("STEP 0: Discover New VC Firms")
    print("=" * 60)

    disc = VCDiscovery()
    existing = disc.get_existing_firms()
    print(f"Existing firms: {len(existing)}")

    result = disc.discover(limit=limit, dry_run=dry_run)

    print(f"\nNew VCs found: {result['new_vcs_found']}")
    if result.get("new_firms"):
        for name in result["new_firms"][:10]:
            print(f"  + {name}")
        if len(result["new_firms"]) > 10:
            print(f"  ... and {len(result['new_firms']) - 10} more")


def step1_discover_urls(limit, dry_run):
    """Find website URLs for VC firms that don't have them."""
    print("\n" + "=" * 60)
    print("STEP 1: Discover VC Firm Website URLs")
    print("=" * 60)

    disc = URLDiscovery()
    missing = disc.get_firms_without_urls()
    print(f"Firms missing URLs: {len(missing)}")

    if not missing:
        print("All firms have URLs. Skipping.")
        return

    result = disc.discover_batch(limit=limit, dry_run=dry_run)
    print(f"\nFound {result['found']} / {result['total']} URLs")


def step2_discover_portfolios(limit, dry_run):
    """Find portfolio companies for VC firms with empty investment lists."""
    print("\n" + "=" * 60)
    print("STEP 2: Discover Portfolio Companies")
    print("=" * 60)

    scraper = PortfolioScraper()
    empty = scraper.get_empty_firms()
    print(f"Firms with empty portfolios: {len(empty)}")

    if not empty:
        print("All firms have portfolio data. Skipping.")
        return

    result = scraper.discover_batch(limit=limit, dry_run=dry_run)

    print(f"\nFirms with companies found: {result['found']}")
    if result.get("results"):
        for r in result["results"][:10]:
            sample = ", ".join(r["sample"][:3])
            print(f"  {r['firm']:40s} {r['count']:3d} companies  ({sample}...)")


def step3_enrich_founders(limit, dry_run):
    """Enrich companies with founder/CEO names and LinkedIn URLs."""
    print("\n" + "=" * 60)
    print("STEP 3: Enrich Founder/CEO Data")
    print("=" * 60)

    engine = EnrichmentEngine()
    stats = engine.get_coverage_stats()
    print(f"Total companies:    {stats['total_companies']}")
    print(f"Already enriched:   {stats['enriched']}")
    print(f"Needing enrichment: {stats['empty']}")
    print(f"Coverage:           {stats['coverage_pct']}%")

    if stats["empty"] == 0:
        print("All companies enriched. Skipping.")
        return

    result = engine.enrich_batch(limit=limit, dry_run=dry_run)
    print(f"\nEnriched: {result['enriched']}  |  Not found: {result['failed']}")


def step4_classify_vcs(limit, dry_run):
    """Classify VCs by sector, stage, and geography."""
    print("\n" + "=" * 60)
    print("STEP 4: Classify VC Investment Focus")
    print("=" * 60)

    classifier = VCClassifier()
    unclassified = classifier.get_unclassified_firms()
    print(f"Firms needing classification: {len(unclassified)}")

    if not unclassified:
        print("All firms classified. Skipping.")
        return

    result = classifier.classify_batch(limit=limit, dry_run=dry_run)

    print(f"\nClassified: {result['classified']} / {result['total']}")
    if result.get("results"):
        for r in result["results"][:10]:
            sectors = ", ".join(r["sectors"][:3]) or "—"
            print(f"  {r['firm']:35s} {sectors}")


def main():
    parser = argparse.ArgumentParser(description="Run the full VC data pipeline")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max items to process per step")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without saving")
    parser.add_argument("--step", type=int, choices=[0, 1, 2, 3, 4], default=None,
                        help="Run only a specific step (0=discover VCs, 1=URLs, 2=portfolios, 3=founders, 4=classify)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    start = time.time()

    print("\n" + "#" * 60)
    print("#  VC LinkedIn Connector — Data Pipeline")
    print("#" * 60)
    if args.dry_run:
        print("  MODE: Dry run (no files will be modified)")
    if args.limit:
        print(f"  LIMIT: {args.limit} items per step")

    steps = [0, 1, 2, 3, 4] if args.step is None else [args.step]

    if 0 in steps:
        step0_discover_vcs(args.limit, args.dry_run)

    if 1 in steps:
        step1_discover_urls(args.limit, args.dry_run)

    if 2 in steps:
        step2_discover_portfolios(args.limit, args.dry_run)

    if 3 in steps:
        step3_enrich_founders(args.limit, args.dry_run)

    if 4 in steps:
        step4_classify_vcs(args.limit, args.dry_run)

    elapsed = time.time() - start
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)

    print("\n" + "#" * 60)
    print(f"#  Pipeline complete in {mins}m {secs}s")
    print("#" * 60 + "\n")


if __name__ == "__main__":
    main()
