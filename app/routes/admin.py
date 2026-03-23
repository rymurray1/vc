"""
Admin routes for the scraper and enrichment engine.
Dashboard to monitor coverage, trigger enrichment runs, and view progress.
"""

import sys
import threading
import logging
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

# Add scraper to path
scraper_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(scraper_root))

from scraper.enrichment import EnrichmentEngine

logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__, url_prefix='/admin')

# Shared enrichment engine instance
_engine = None
_enrichment_thread = None


def _get_engine():
    """Get or create the enrichment engine."""
    global _engine
    if _engine is None:
        _engine = EnrichmentEngine()
    return _engine


@bp.route('/')
def dashboard():
    """Admin dashboard with coverage stats and enrichment controls."""
    if 'username' not in session:
        return redirect(url_for('main.index'))

    engine = _get_engine()
    stats = engine.get_coverage_stats()
    incomplete = engine.get_incomplete_companies()

    return render_template(
        'admin.html',
        stats=stats,
        incomplete_sample=incomplete[:20],
        incomplete_total=len(incomplete),
        progress=engine.progress,
    )


@bp.route('/enrich', methods=['POST'])
def start_enrichment():
    """Start an enrichment run in the background."""
    global _enrichment_thread

    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    engine = _get_engine()

    # Don't start if already running
    if engine.progress.get("status") == "running":
        return jsonify({'error': 'Enrichment already running'}), 409

    data = request.get_json() or {}
    limit = data.get('limit', 10)
    dry_run = data.get('dry_run', False)

    # Cap limit to prevent accidental massive runs
    limit = min(int(limit), 500)

    def run_enrichment():
        try:
            engine.enrich_batch(limit=limit, dry_run=dry_run)
        except Exception as e:
            logger.error(f"Enrichment error: {e}")
            engine.progress["status"] = "error"
            engine.progress["errors"].append(str(e))

    _enrichment_thread = threading.Thread(target=run_enrichment, daemon=True)
    _enrichment_thread.start()

    return jsonify({'status': 'started', 'limit': limit, 'dry_run': dry_run})


@bp.route('/status')
def enrichment_status():
    """Return current enrichment progress as JSON."""
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    engine = _get_engine()
    return jsonify(engine.progress)


@bp.route('/companies')
def list_companies():
    """Return companies filtered by enrichment status."""
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    engine = _get_engine()
    filter_type = request.args.get('filter', 'empty')  # 'empty', 'enriched', 'all'
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    founders_data = engine._load_founders()

    if filter_type == 'empty':
        companies = {k: v for k, v in founders_data.items() if not v.get("founders")}
    elif filter_type == 'enriched':
        companies = {k: v for k, v in founders_data.items() if v.get("founders")}
    else:
        companies = founders_data

    # Paginate
    company_list = list(companies.items())
    total = len(company_list)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = company_list[start:end]

    result = []
    for name, data in page_items:
        result.append({
            'name': name,
            'url': data.get('url', ''),
            'founders': data.get('founders', []),
            'ceo': data.get('ceo', {}),
        })

    return jsonify({
        'companies': result,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
    })


@bp.route('/test-scraper')
def test_scraper():
    """Quick test endpoint to verify the scraper is working."""
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    query = request.args.get('q', 'OpenAI founder CEO')

    from scraper import search
    result = search(query)

    if result is None:
        return jsonify({'error': 'Scraper returned no results (may be blocked)'}), 500

    return jsonify({
        'query': query,
        'organic_count': len(result.get('organic', [])),
        'has_knowledge_graph': bool(result.get('knowledgeGraph')),
        'results': result,
    })
