# VC LinkedIn Connector

## Project Overview
Maps your LinkedIn connections to people in the VC ecosystem. Given a user's LinkedIn connections, it shows which of their connections are founders/CEOs of VC-backed companies and which VCs back those companies. Users can filter by VC sector, stage, and geography to find warm intro paths to specific types of investors.

## Current Status (as of 2026-03-23)

### What's Running
- **Step 1 (URL discovery) is running on the ThinkPad server** via Tor proxy
- ~450 of 720 firms have URLs, ~270 remaining
- Server: ThinkPad X1 Carbon (Linux), repo at `~/vc`, using Python venv

### What's Done
- Internal scraper built (replaced Serper.dev — no paid APIs)
- DuckDuckGo Lite + Brave Search dual-engine with automatic fallback
- Tor proxy integration for IP rotation (eliminates rate limiting)
- 5-step pipeline: discover VCs → find URLs → find portfolios → enrich founders → classify sectors
- All scripts are resumable (save after each item, skip already-filled data)
- Flask admin dashboard at `/admin`

### What's Next
- Step 1 finishes → run Steps 2-4 on server
- Portfolio scraper (Step 2) needs refinement — most VC sites are JS-rendered, direct scraping gets empty shells. Search-based "backed by" extraction works but yields fewer results per firm
- URL scoring needs tuning — some results point to aggregator sites instead of the VC's actual website
- Set up cron job for nightly runs once pipeline is validated
- Clean up bad URLs after Step 1 completes

## How It All Works

### The Data Chain
Three JSON files form the core data pipeline:

```
vc_tags.json              firms.json                founders.json
────────────              ──────────                ─────────────
VC firm metadata          VC → portfolio            Company → founders
(website, sectors,        companies                 (names + LinkedIn URLs)
 stage, geography)
```

**Flow**: VC Firm → what companies they invested in → who runs those companies + LinkedIn URLs

### The Matching Algorithm (`app/matcher.py`)
1. User syncs their LinkedIn connections (each has a LinkedIn URL)
2. User picks filters (sector, geography, etc.)
3. Matcher extracts LinkedIn URL slugs from user connections
4. Matcher extracts LinkedIn URL slugs from founders/CEOs in the database
5. **Exact slug match** — if user's connection slug matches a founder's slug, that's a warm intro path
6. Output: "You know **Person X** → they founded **Company Y** → backed by **VC Z**"

## Internal Scraper (`scraper/`)
Replaced Serper.dev with a free, internal search engine. Uses DuckDuckGo Lite + Brave Search as fallback. Tor proxy for IP rotation.

### Architecture
- `scraper/google.py` — DuckDuckGo Lite scraper (primary engine)
- `scraper/brave.py` — Brave Search scraper (fallback when DDG is rate-limited)
- `scraper/__init__.py` — `MultiScraper` class that tries DDG then Brave automatically
- `scraper/parser.py` — HTML parsing for DDG Lite results
- `scraper/config.py` — Rate limits, user agent rotation, retry settings, Tor proxy config
- Returns same format as Serper.dev: `{"organic": [{"title", "link", "snippet"}]}`

### The 5-Step Pipeline

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 0 | `scraper/run_discover_vcs.py` | DDG/Brave search queries | New VC firms added to `vc_tags.json` + `firms.json` |
| 1 | `scraper/run_discover_urls.py` | `vc_tags.json` (firms without websites) | Website URLs saved to `vc_tags.json` |
| 2 | `scraper/run_discover_portfolios.py` | `firms.json` (firms with empty portfolios) | Portfolio companies saved to `firms.json` + new companies added to `founders.json` |
| 3 | `scraper/run_enrich.py` | `founders.json` (companies without founder data) | Founder names + LinkedIn URLs saved to `founders.json` |
| 4 | `scraper/run_classify_vcs.py` | `vc_tags.json` (firms with generic tags) | Sector, stage, geography tags saved to `vc_tags.json` |

### Running the Scrapers

**On ThinkPad server (Linux):**
```bash
cd ~/vc
source venv/bin/activate

# Run a specific step in background (survives closing SSH):
nohup python3 scraper/run_all.py --step 1 > scraper.log 2>&1 &

# Run steps 1-4 (skip step 0 if VC list is up to date):
nohup python3 scraper/run_all.py --step 1 > scraper.log 2>&1 &
# Then after step 1 finishes:
nohup python3 scraper/run_all.py --step 2 > scraper.log 2>&1 &
# etc.

# Check progress:
tail -f scraper.log

# Check if running:
ps aux | grep python3

# Kill it:
kill -9 $(pgrep -f run_all)
```

**On Windows laptop (PowerShell):**
```powershell
& "C:\Users\arthu\AppData\Local\Microsoft\WindowsApps\python3.exe" scraper\run_all.py
```

All scripts support `--limit N` and `--dry-run`. All are resumable.

### Tor Proxy Setup (ThinkPad server)
Tor rotates IP every 10 minutes automatically. Eliminates rate limiting.
```bash
sudo apt install tor
sudo systemctl start tor
sudo systemctl enable tor
pip install "httpx[socks]"
```
Config in `scraper/config.py`: `TOR_PROXY = "socks5://127.0.0.1:9050"`
Set to `None` to disable Tor.

### Git Workflow (laptop ↔ server)
```bash
# Push from laptop:
cd "vc-github cloned"
git add -A && git commit -m "message" && git push

# Pull on server:
cd ~/vc && git pull

# After scraper finishes on server, push updated data:
git add -A && git commit -m "Updated VC data" && git push

# Pull fresh data back to laptop:
git pull
```

### Rate Limiting Notes
- DDG Lite: returns HTTP 202 when throttled. With Tor, this rarely happens.
- Brave Search: returns HTTP 429 when throttled. Fallback engine, used when DDG fails.
- Without Tor: ~50-100 requests before throttling. With Tor: unlimited.
- Delays between requests: 4-7 seconds (configurable in config.py)
- Max retries per engine: 2 (fail fast, try the other engine)

### VC Classification Taxonomy
Step 4 classifies VCs into:
- **Sectors**: AI/ML, Biotech, Healthcare, Fintech, Climate/Energy, SaaS/Enterprise, Consumer, Industrials/Manufacturing, Crypto/Web3, Real Estate, Food/Ag, Education, Cybersecurity, Deep Tech/Frontier
- **Stages**: Pre-Seed/Seed, Early Stage, Growth, Late Stage, Multi-Stage
- **Geography**: US, Europe, Global, Asia, Emerging Markets

## Data Files (in repo root)

### `vc_tags.json` — VC Firm Metadata (720 firms)
```json
{
  "Andreessen Horowitz": {
    "focus": ["deep tech", "general"],
    "ma_presence": false,
    "hq": "San Francisco, CA",
    "website": "https://a16z.com/",
    "sectors": ["Consumer", "AI / Machine Learning", "SaaS / Enterprise"],
    "stages": ["Early Stage", "Growth"],
    "geography": ["US"]
  }
}
```

### `firms.json` — VC Portfolios (601 firms, 7,311 investments)
```json
[
  {
    "name": "Sequoia Capital",
    "country": "United States",
    "investments": [
      {"company": "Stripe", "url": "https://stripe.com"},
      {"company": "Figma", "url": "https://figma.com"}
    ]
  }
]
```
- 106 firms with portfolio data populated
- 495 firms with empty investments (to be filled by Step 2)

### `founders.json` — Founder/CEO Data (5,022 companies)
```json
{
  "Stripe": {
    "url": "https://stripe.com",
    "founders": [
      {"name": "Patrick Collison", "linkedin": "https://linkedin.com/in/patrickcollison"}
    ],
    "ceo": {"name": "Patrick Collison", "linkedin": "https://linkedin.com/in/patrickcollison"}
  }
}
```
- 4,496 enriched with founder data (89.5% coverage)
- 526 companies still need enrichment

## Flask Web App (`app/`)

### Running
```bash
python3 run.py
# → http://localhost:5000
```

### Routes
- `/` — Login
- `/dashboard` — User dashboard with connection stats
- `/search` — Search connections and VCs
- `/results` — Warm intro path results (filterable)
- `/admin/` — Enrichment dashboard (coverage stats, trigger scraper runs, test queries)
- `/api/connections` — Bookmarklet endpoint to sync LinkedIn connections

### Dependencies
```
Flask, Flask-SQLAlchemy, httpx[socks], beautifulsoup4
```

## Legacy (Reference Only)

### Original Serper.dev Scripts (`enricher/`, `enrich_founders_serper.py`, etc.)
- Used Serper.dev paid API ($) for Google search
- Hardcoded paths to `/Users/ryanmurray/...`
- Replaced by the internal `scraper/` module
- Kept for reference but no longer the active pipeline

### Agent-Based Approach (`batches/`, `process_batch.sh`, etc.)
- Used Claude Haiku agents with web search
- Completed 9/74 batches before being replaced
- Kept for reference

## Key Decisions
- **DuckDuckGo + Brave dual-engine** — DDG Lite as primary (plain HTML via POST), Brave as fallback. Automatic failover.
- **Tor for IP rotation** — free, rotates every 10 min, eliminates rate limiting entirely
- **Replaced Serper.dev** — built internal scraper to eliminate paid API dependency ($0/month)
- **LinkedIn slug matching** — exact URL slug comparison for zero false positives
- **Sequential pipeline** — Steps 0→1→2→3→4 because each depends on the previous step's output
- **Save-as-you-go** — every script saves after each item, safe to kill and restart
- **Sector classification** — enables filtering VCs by investment thesis (biotech, fintech, etc.)
- **Git-based sync** — laptop pushes code, server pulls and runs, server pushes data back
