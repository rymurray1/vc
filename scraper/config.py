"""
Configuration for the Google SERP scraper.
Rate limits, user agents, retry settings.
"""

import random

# Request timing
MIN_DELAY = 2.0  # Minimum seconds between requests
MAX_DELAY = 4.0  # Maximum seconds between requests
MULTI_QUERY_DELAY = 0.5  # Delay between multi-strategy queries for same company

# Retry settings
MAX_RETRIES = 5
BACKOFF_BASE = 2  # Exponential backoff base (2^retry seconds)
BACKOFF_MAX = 30  # Max backoff in seconds

# HTTP settings
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 15
NUM_RESULTS = 10

# Google search URL
GOOGLE_SEARCH_URL = "https://www.google.com/search"

# Real browser user agents (Chrome, Firefox, Edge on Windows/Mac)
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]

# Standard browser headers (sans User-Agent which rotates)
BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# CAPTCHA / block detection markers in response HTML
BLOCK_MARKERS = [
    "detected unusual traffic",
    "captcha",
    "recaptcha",
    "/sorry/index",
    "unusual traffic from your computer",
    "systems have detected unusual traffic",
]


def get_random_headers():
    """Return headers with a random user agent."""
    headers = BASE_HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    return headers


def get_random_delay():
    """Return a random delay between MIN_DELAY and MAX_DELAY."""
    return random.uniform(MIN_DELAY, MAX_DELAY)


def get_backoff_delay(retry_num):
    """Return exponential backoff delay for a given retry number."""
    delay = min(BACKOFF_BASE ** retry_num, BACKOFF_MAX)
    # Add jitter
    return delay + random.uniform(0, 1)
