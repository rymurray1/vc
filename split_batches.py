#!/usr/bin/env python3
"""Split founders.json incomplete entries into batches of 50."""
import json, os

FOUNDERS_FILE = "/Users/ryanmurray/programming/vc/founders.json"
BATCHES_DIR = "/Users/ryanmurray/programming/vc/batches"
BATCH_SIZE = 50

def split():
    data = json.load(open(FOUNDERS_FILE))
    incomplete = {k: v for k, v in data.items() if not v["founders"]}
    keys = sorted(incomplete.keys())
    print(f"Incomplete: {len(keys)} companies → {-(-len(keys)//BATCH_SIZE)} batches")
    for i in range(0, len(keys), BATCH_SIZE):
        batch_keys = keys[i:i+BATCH_SIZE]
        batch = {k: incomplete[k] for k in batch_keys}
        n = i // BATCH_SIZE + 1
        path = f"{BATCHES_DIR}/batch_{n:03d}.json"
        json.dump(batch, open(path, "w"), indent=2)
    print(f"Written to {BATCHES_DIR}/")

def merge():
    """Merge completed batches back into founders.json."""
    data = json.load(open(FOUNDERS_FILE))
    updated = 0
    for fname in sorted(os.listdir(BATCHES_DIR)):
        if not fname.endswith(".json"):
            continue
        batch = json.load(open(f"{BATCHES_DIR}/{fname}"))
        for k, v in batch.items():
            if v["founders"]:  # only merge if filled in
                data[k] = v
                updated += 1
    json.dump(data, open(FOUNDERS_FILE, "w"), indent=2)
    print(f"Merged {updated} updated entries into {FOUNDERS_FILE}")

def status():
    """Show batch completion status."""
    files = sorted(f for f in os.listdir(BATCHES_DIR) if f.endswith(".json"))
    total_companies = done_companies = 0
    pending_batches = []
    for fname in files:
        batch = json.load(open(f"{BATCHES_DIR}/{fname}"))
        n = len(batch)
        filled = sum(1 for v in batch.values() if v["founders"])
        total_companies += n
        done_companies += filled
        if filled < n:
            pending_batches.append(f"{fname}: {filled}/{n}")
    print(f"Overall: {done_companies}/{total_companies} companies complete across {len(files)} batches")
    if pending_batches:
        print(f"Pending batches ({len(pending_batches)}):")
        for b in pending_batches[:20]:
            print(f"  {b}")
        if len(pending_batches) > 20:
            print(f"  ... and {len(pending_batches)-20} more")

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "split"
    {"split": split, "merge": merge, "status": status}[cmd]()
