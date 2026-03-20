# VC Intro Paths

A local multi-user web app to find warm introduction paths to deep tech / green tech / energy tech VCs through LinkedIn connections.

## Setup & Installation

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Quick Start

1. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app:**
   ```bash
   python3 run.py
   ```

4. **Visit the app:**
   Open http://localhost:5000 in your browser

## Usage

### 1. Enter Your Name
- Open http://localhost:5000
- Enter your name (e.g., "Matt Millard")
- Click "Get Started"

### 2. Set Up Bookmarklet
- On your dashboard, drag the **"📱 Sync from LinkedIn"** link to your browser's bookmark bar
- The bookmarklet contains your unique sync token

### 3. Sync LinkedIn Connections
- Go to [LinkedIn Connections](https://www.linkedin.com/mynetwork/invite-connect/connections/)
- Click the bookmarklet in your bookmark bar
- The app will scrape visible connections and auto-scroll to load all
- You'll see a toast notification: "✓ X connections synced"

### 4. Find Intro Paths
- Back on the dashboard, select:
  - Focus areas: ☑ Deep Tech  ☑ Green Tech  ☑ Energy Tech
  - Optionally: ☑ MA-based VCs only
- Click "Find Intro Paths"
- Results show: VC firm → portfolio company → founder name/link → your connection

### 5. Export Results
- Click "📥 Download as CSV" to export intro paths

### 6. Switch Users
- Click "Logout" in the navbar to go back to the name entry screen
- Enter a different name to work with separate connection sets

## Architecture

**Stack:**
- Flask (Python web framework)
- SQLite (database for users & connections)
- Flask-Login (session management)
- Jinja2 (HTML templates)

**Data Files:**
- `firms.json` - 95 VC firms with portfolios
- `founders.json` - 4,199 portfolio companies with founder info
- `vc_tags.json` - Focus areas & MA presence metadata

**Runs:** Localhost only (http://127.0.0.1:5000)

## Project Structure

```
vc/
├── app/
│   ├── __init__.py           # Flask factory
│   ├── models.py             # User & Connection models
│   ├── matcher.py            # Core matching logic
│   ├── routes/
│   │   └── main.py           # Home, dashboard, results, bookmarklet API, logout
│   ├── templates/
│   │   ├── base.html         # Layout with navbar
│   │   ├── index.html        # Username entry screen
│   │   ├── dashboard.html    # Sync status, bookmarklet, filters
│   │   └── results.html      # Intro paths display
│   └── static/
│       └── style.css         # Styling
├── run.py                    # Entry point
├── requirements.txt
├── firms.json
├── founders.json
├── vc_tags.json
└── README.md
```

## Database Schema

**Users table:**
- `id`, `username`, `sync_token` (UUID), `created_at`

**Connections table (per user):**
- `id`, `user_id`, `name`, `title`, `linkedin_url`, `slug`, `synced_at`

## Testing the App

Test the full user flow:
```bash
source venv/bin/activate
python3 << 'EOF'
from app import create_app

app = create_app()
client = app.test_client()

# 1. Get home page
response = client.get('/')
print(f"Home page: {response.status_code}")

# 2. Submit username
response = client.post('/', data={'username': 'Test User'})
print(f"Username submission: {response.status_code}")

# 3. Access dashboard
with client:
    client.post('/', data={'username': 'Test User'})
    response = client.get('/dashboard')
    print(f"Dashboard: {response.status_code}")

print("✓ Basic flow works")
EOF
```

Test matching logic:
```bash
python3 -c "from app.matcher import get_vcs_by_focus; vcs = get_vcs_by_focus(['deep tech'], ma_only=True); print(f'Found {len(vcs)} MA-based deep tech VCs')"
```

## Notes

- No password required — just enter your name to get started
- The app stores data in `app.db` (SQLite) in the project root
- Each user has a unique `sync_token` UUID for the bookmarklet
- Connections are per-user and can be re-synced (replaces existing set)
- Multiple users can use the app with separate connection sets
- Slug matching is case-insensitive and extracts LinkedIn profile ID from URLs
- Logout clears your session; enter your name again to resume