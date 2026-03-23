#!/usr/bin/env python3
"""
Classify VC firms by sector, stage, and geography.
Searches for each firm's investment thesis and assigns tags like:
  Sectors:   "Biotech / Life Sciences", "Fintech", "AI / Machine Learning"
  Stages:    "Early Stage", "Growth", "Seed"
  Geography: "US", "Europe", "Global"

Saves to vc_tags.json so the app can filter VCs by category.

Usage:
    python run_classify_vcs.py                # Classify all unclassified firms
    python run_classify_vcs.py --limit 20     # Only process 20 firms
    python run_classify_vcs.py --dry-run      # Preview without saving
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.vc_classifier import VCClassifier


def main():
    parser = argparse.ArgumentParser(description="Classify VC firms by sector/stage")
    parser.add_argument("--limit", type=int, default=None, help="Max firms to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    classifier = VCClassifier()
    unclassified = classifier.get_unclassified_firms()

    print(f"\nVC Classification")
    print(f"{'=' * 60}")
    print(f"Firms needing classification: {len(unclassified)}")
    if args.limit:
        print(f"Processing limit:            {args.limit}")
    print(f"Dry run:                     {args.dry_run}")
    print(f"{'=' * 60}\n")

    result = classifier.classify_batch(limit=args.limit, dry_run=args.dry_run)

    print(f"\n{'=' * 60}")
    print(f"Done. Classified {result['classified']} / {result['total']} firms")
    print()

    if result.get("results"):
        for r in result["results"][:15]:
            sectors = ", ".join(r["sectors"][:3]) or "—"
            stages = ", ".join(r["stages"][:2]) or "—"
            geo = ", ".join(r["geography"][:2]) or "—"
            print(f"  {r['firm']:35s} {sectors}")
            print(f"  {'':35s} Stage: {stages} | Geo: {geo}")
            print()

    if not args.dry_run and result["classified"] > 0:
        print(f"Saved to vc_tags.json")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
