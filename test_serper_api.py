#!/usr/bin/env python3
"""
Test Serper API connectivity and key validity.
"""

import os
import sys
import requests

ENV_FILE = "/Users/ryanmurray/programming/vc/enricher/.env"

def load_api_key():
    """Load Serper API key from .env file."""
    if not os.path.exists(ENV_FILE):
        print(f"ERROR: {ENV_FILE} not found")
        return None
    with open(ENV_FILE) as f:
        for line in f:
            if line.startswith("SERPER_API_KEY="):
                key = line.split("=", 1)[1].strip()
                if key and key != "your_api_key_here":
                    return key
    return None

def test_serper_api(api_key):
    """Test Serper API with a simple query."""
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    payload = {"q": "Tesla founder CEO", "num": 5}

    print(f"Testing Serper API...")
    print(f"API Key: {api_key[:20]}...")
    print(f"URL: {url}")
    print(f"Query: {payload['q']}")
    print()

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print(f"\nSUCCESS! Got response with {len(data.get('organic', []))} results")
            if data.get('organic'):
                print(f"First result: {data['organic'][0].get('title', 'N/A')}")
            return True
        else:
            print(f"\nERROR: HTTP {response.status_code}")
            print(f"Response body: {response.text[:500]}")
            return False
    except Exception as e:
        print(f"\nEXCEPTION: {type(e).__name__}: {e}")
        return False

def main():
    api_key = load_api_key()
    if not api_key:
        print("ERROR: Could not load API key from .env file")
        sys.exit(1)

    success = test_serper_api(api_key)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
