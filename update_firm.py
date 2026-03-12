#!/usr/bin/env python3
"""Helper to update a specific VC's investments in firms.json"""
import json, sys, os

FIRMS_FILE = "/Users/ryanmurray/programming/vc/firms.json"

def load():
    with open(FIRMS_FILE) as f:
        return json.load(f)

def save(data):
    with open(FIRMS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {FIRMS_FILE}")

def update_firm(firm_name, investments):
    """investments: list of {"company": str, "url": str}"""
    data = load()
    for firm in data:
        if firm["name"].lower() == firm_name.lower():
            firm["investments"] = investments
            save(data)
            print(f"Updated '{firm_name}' with {len(investments)} investments.")
            return
    print(f"ERROR: Firm '{firm_name}' not found.")

def show_firm(firm_name):
    data = load()
    for firm in data:
        if firm["name"].lower() == firm_name.lower():
            print(f"{firm['name']}: {len(firm['investments'])} investments")
            return
    print(f"Not found: {firm_name}")

def stats():
    data = load()
    total = sum(len(f["investments"]) for f in data)
    done = [f["name"] for f in data if f["investments"]]
    pending = [f["name"] for f in data if not f["investments"]]
    print(f"Total investments: {total}")
    print(f"Firms with data ({len(done)}): {', '.join(done)}")
    print(f"Firms pending ({len(pending)}): {', '.join(pending)}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats()
