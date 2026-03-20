import csv
import io
import os
import json
from pathlib import Path
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file, session, flash
from werkzeug.utils import secure_filename
from app import db
from app.models import Connection, User
from app.matcher import extract_linkedin_slug, get_vcs_by_focus, find_intro_paths

bp = Blueprint('main', __name__)


@bp.route('/', methods=['GET', 'POST'])
def index():
    """Home page - login page."""
    if 'username' in session:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password required', 'error')
            return render_template('index.html')

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash('Invalid username or password', 'error')
            return render_template('index.html')

        session['username'] = username
        return redirect(url_for('main.dashboard'))

    return render_template('index.html')


@bp.route('/dashboard')
def dashboard():
    """Show user dashboard with sync status and upload form."""
    if 'username' not in session:
        return redirect(url_for('main.index'))

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return redirect(url_for('main.index'))

    connection_count = Connection.query.filter_by(user_id=user.id).count()
    last_sync = Connection.query.filter_by(user_id=user.id).order_by(Connection.synced_at.desc()).first()
    last_sync_time = last_sync.synced_at if last_sync else None

    return render_template(
        'dashboard.html',
        username=session['username'],
        connection_count=connection_count,
        last_sync_time=last_sync_time,
        sync_token=user.sync_token
    )


@bp.route('/upload-csv', methods=['POST'])
def upload_csv():
    """Handle CSV file upload of LinkedIn connections."""
    if 'username' not in session:
        return redirect(url_for('main.index'))

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return redirect(url_for('main.index'))

    # Check if file was uploaded
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('main.dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('main.dashboard'))

    if not file.filename.endswith('.csv'):
        flash('File must be a CSV', 'error')
        return redirect(url_for('main.dashboard'))

    try:
        # Read CSV file
        stream = io.TextIOWrapper(file.stream, encoding='utf-8')
        reader = csv.DictReader(stream)

        if not reader.fieldnames:
            flash('Invalid CSV file', 'error')
            return redirect(url_for('main.dashboard'))

        # Parse CSV - LinkedIn format has columns like:
        # First Name, Last Name, Email Address, Company, Position, Connected On
        # We'll look for variations
        count = 0
        for row in reader:
            # Try to extract name
            if 'First Name' in row and 'Last Name' in row:
                name = f"{row['First Name']} {row['Last Name']}".strip()
            elif 'Name' in row:
                name = row['Name'].strip()
            else:
                continue

            # Try to extract title/position
            title = row.get('Position', '')

            # Try to extract LinkedIn URL
            linkedin_url = row.get('Profile URL', '') or row.get('linkedin_url', '')

            if not name:
                continue

            # Extract slug from URL if available
            slug = None
            if linkedin_url:
                slug = extract_linkedin_slug(linkedin_url)

            # Only add if we have a name and ideally a slug for matching
            if name and slug:
                existing = Connection.query.filter_by(user_id=user.id, slug=slug).first()
                if existing:
                    existing.name = name
                    existing.title = title
                    existing.linkedin_url = linkedin_url
                    existing.synced_at = datetime.utcnow()
                else:
                    new_conn = Connection(
                        user_id=user.id,
                        name=name,
                        title=title,
                        linkedin_url=linkedin_url,
                        slug=slug
                    )
                    db.session.add(new_conn)
                count += 1

        db.session.commit()
        flash(f'✓ {count} connections synced from CSV', 'success')

    except Exception as e:
        flash(f'Error parsing CSV: {str(e)}', 'error')

    return redirect(url_for('main.dashboard'))


@bp.route('/api/connections', methods=['POST'])
def sync_connections():
    """Bookmarklet endpoint to sync LinkedIn connections."""
    token = request.args.get('token')
    data = request.get_json() or {}

    # Verify token
    user = User.query.filter_by(sync_token=token).first()
    if not user:
        return jsonify({'status': 'error', 'message': 'Invalid token'}), 401

    connections = data.get('connections', [])
    if not connections:
        return jsonify({'status': 'error', 'message': 'No connections provided'}), 400

    # Upsert connections
    count = 0
    for conn in connections:
        slug = extract_linkedin_slug(conn.get('linkedin_url', ''))
        if not slug:
            continue

        # Check if connection already exists
        existing = Connection.query.filter_by(
            user_id=user.id,
            slug=slug
        ).first()

        if existing:
            # Update existing
            existing.name = conn.get('name', '')
            existing.title = conn.get('title', '')
            existing.linkedin_url = conn.get('linkedin_url', '')
            existing.synced_at = datetime.utcnow()
        else:
            # Create new
            new_conn = Connection(
                user_id=user.id,
                name=conn.get('name', ''),
                title=conn.get('title', ''),
                linkedin_url=conn.get('linkedin_url', ''),
                slug=slug
            )
            db.session.add(new_conn)

        count += 1

    db.session.commit()
    return jsonify({'status': 'ok', 'count': count}), 200


@bp.route('/results', methods=['GET', 'POST'])
def results():
    """Display intro path results."""
    if 'username' not in session:
        return redirect(url_for('main.index'))

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        # Process form submission and find results
        focus_areas = request.form.getlist('focus')
        ma_only = request.form.get('ma_only') == 'on'

        if not focus_areas:
            focus_areas = ['deep tech', 'green tech', 'energy tech']

        # Get user connections
        connections = Connection.query.filter_by(user_id=user.id).all()
        user_connections = [
            {
                'name': c.name,
                'title': c.title,
                'slug': c.slug,
                'linkedin_url': c.linkedin_url
            }
            for c in connections
        ]

        # Get filtered VCs
        filtered_vcs = get_vcs_by_focus(focus_areas, ma_only)
        vc_names = [vc['name'] for vc in filtered_vcs]

        # Find intro paths
        intro_paths = find_intro_paths(user_connections, vc_names)

        # Store results in session for display
        return render_template('results.html', results=intro_paths, focus_areas=focus_areas, ma_only=ma_only, username=session['username'])

    # GET request - display cached results if available
    return render_template('results.html', results=[], focus_areas=[], ma_only=False, username=session['username'])


@bp.route('/results/download', methods=['POST'])
def download_results():
    """Download results as CSV."""
    if 'username' not in session:
        return redirect(url_for('main.index'))

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return redirect(url_for('main.index'))

    # Get form data from request
    focus_areas = request.form.getlist('focus')
    ma_only = request.form.get('ma_only') == 'on'

    if not focus_areas:
        focus_areas = ['deep tech', 'green tech', 'energy tech']

    # Get user connections
    connections = Connection.query.filter_by(user_id=user.id).all()
    user_connections = [
        {
            'name': c.name,
            'title': c.title,
            'slug': c.slug,
            'linkedin_url': c.linkedin_url
        }
        for c in connections
    ]

    # Get filtered VCs
    filtered_vcs = get_vcs_by_focus(focus_areas, ma_only)
    vc_names = [vc['name'] for vc in filtered_vcs]

    # Find intro paths
    intro_paths = find_intro_paths(user_connections, vc_names)

    # Create CSV
    output = io.StringIO()
    fieldnames = [
        'vc_firm', 'portfolio_company', 'person_role', 'person_name',
        'person_linkedin', 'connection_name', 'connection_title'
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for result in intro_paths:
        writer.writerow({
            'vc_firm': result['vc'],
            'portfolio_company': result['company'],
            'person_role': result['person_role'],
            'person_name': result['person_name'],
            'person_linkedin': result['person_linkedin'],
            'connection_name': result['connection_name'],
            'connection_title': result['connection_title']
        })

    # Return as file download
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'intro_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )


@bp.route('/load-connections')
def load_connections():
    """Load connections from CSV in connections/ directory."""
    if 'username' not in session:
        return redirect(url_for('main.index'))

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return redirect(url_for('main.index'))

    # Find CSV files in connections/ directory
    base_dir = Path(__file__).parent.parent.parent
    connections_dir = base_dir / 'connections'

    if not connections_dir.exists():
        flash('No connections directory found', 'error')
        return redirect(url_for('main.dashboard'))

    # Get most recent CSV file
    csv_files = sorted(connections_dir.glob('linkedin-connections-*.csv'), reverse=True)
    if not csv_files:
        flash('No CSV files found in connections/ directory', 'error')
        return redirect(url_for('main.dashboard'))

    csv_path = csv_files[0]

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0

            for row in reader:
                # Extract from LinkedIn export format
                name = row.get('Name', '').strip()
                title = row.get('Title', '').strip()
                linkedin_url = row.get('Linkedin URL', '').strip()

                if not name or not linkedin_url:
                    continue

                slug = extract_linkedin_slug(linkedin_url)
                if not slug:
                    continue

                # Upsert connection
                existing = Connection.query.filter_by(user_id=user.id, slug=slug).first()
                if existing:
                    existing.name = name
                    existing.title = title
                    existing.linkedin_url = linkedin_url
                    existing.synced_at = datetime.utcnow()
                else:
                    new_conn = Connection(
                        user_id=user.id,
                        name=name,
                        title=title,
                        linkedin_url=linkedin_url,
                        slug=slug
                    )
                    db.session.add(new_conn)
                count += 1

            db.session.commit()
            flash(f'✓ Loaded {count} connections from {csv_path.name}', 'success')

    except Exception as e:
        flash(f'Error loading connections: {str(e)}', 'error')

    return redirect(url_for('main.dashboard'))


@bp.route('/logout')
def logout():
    """Clear session and go back to home."""
    session.clear()
    return redirect(url_for('main.index'))


@bp.route('/search')
def search():
    """Search connections and VCs page."""
    if 'username' not in session:
        return redirect(url_for('main.index'))

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return redirect(url_for('main.index'))

    # Check if user has connections synced
    connection_count = Connection.query.filter_by(user_id=user.id).count()
    connections_loaded = connection_count > 0

    return render_template('search.html', connections_loaded=connections_loaded)


@bp.route('/api/search-vcs')
def api_search_vcs():
    """Get list of VCs from warm intro map."""
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        base_dir = Path(__file__).parent.parent.parent
        warm_intro_path = base_dir / 'warm_intro_map.json'

        if not warm_intro_path.exists():
            return jsonify({'vcs': []})

        with open(warm_intro_path, 'r') as f:
            data = json.load(f)

        # Extract VCs from the energy_vcs section
        vcs = []
        if 'energy_vcs' in data:
            for vc_name, vc_data in data['energy_vcs'].items():
                vcs.append({
                    'name': vc_name,
                    'hq': vc_data.get('hq'),
                    'tags': vc_data.get('tags', []),
                    'ma_presence': vc_data.get('ma_presence', False),
                    'intros_available': vc_data.get('intros_available', [])
                })

        return jsonify({'vcs': vcs})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/search-people')
def api_search_people():
    """Get list of people from LinkedIn VC map."""
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        base_dir = Path(__file__).parent.parent.parent
        linkedin_map_path = base_dir / 'linkedin_vc_map_all.json'

        if not linkedin_map_path.exists():
            return jsonify({'people': []})

        with open(linkedin_map_path, 'r') as f:
            data = json.load(f)

        # Convert to list of people
        people = []
        for person_name, person_data in data.items():
            people.append({
                'name': person_name,
                'linkedin': person_data.get('linkedin'),
                'companies_founded': person_data.get('companies_founded', [])
            })

        return jsonify({'people': people})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
