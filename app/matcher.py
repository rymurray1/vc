import json
from pathlib import Path
from difflib import SequenceMatcher


def extract_linkedin_slug(url):
    """Extract LinkedIn slug from URL, normalized."""
    if not url or not isinstance(url, str):
        return None

    # Remove trailing slashes and whitespace
    url = url.strip().rstrip('/')

    # Extract the slug (last part of the path)
    # Handle both linkedin.com/in/slug and www.linkedin.com/in/slug
    if '/in/' in url:
        slug = url.split('/in/')[-1]
        # Remove any query params or fragments
        slug = slug.split('?')[0].split('#')[0].strip('/')
        return slug.lower()

    return None


def get_vcs_by_focus(focus_areas, ma_only=False):
    """
    Get list of VC firms filtered by focus areas and MA presence.

    Args:
        focus_areas: list of strings like ['deep tech', 'green tech']
        ma_only: if True, only return VCs with MA presence

    Returns:
        list of dicts with 'name' and other metadata from vc_tags.json
    """
    # Determine the base directory where JSON files are stored
    base_dir = Path(__file__).parent.parent

    with open(base_dir / 'vc_tags.json') as f:
        vc_tags = json.load(f)

    result = []
    for firm_name, metadata in vc_tags.items():
        # Check MA presence if requested
        if ma_only and not metadata.get('ma_presence', False):
            continue

        # Check if firm has any of the requested focus areas
        firm_focus = set(metadata.get('focus', []))
        requested_focus = set(focus_areas)

        if firm_focus & requested_focus:  # Intersection check
            result.append({
                'name': firm_name,
                'focus': metadata.get('focus', []),
                'ma_presence': metadata.get('ma_presence', False),
                'hq': metadata.get('hq', '')
            })

    return result


def find_intro_paths(user_connections, vc_names):
    """
    Find introduction paths from user's connections to portfolio founders.

    Args:
        user_connections: list of dicts with 'name', 'title', 'linkedin_url', 'slug'
        vc_names: list of VC firm names to search

    Returns:
        list of dicts with intro path information
    """
    base_dir = Path(__file__).parent.parent

    # Load founders database
    with open(base_dir / 'founders.json') as f:
        founders_db = json.load(f)

    # Load firms database
    with open(base_dir / 'firms.json') as f:
        firms = json.load(f)

    # Build map of firm names to their portfolio
    firm_portfolio = {}
    for firm in firms:
        if firm['name'] in vc_names:
            companies = [inv['company'] for inv in firm.get('investments', [])]
            firm_portfolio[firm['name']] = companies

    # Build map of connection slugs for quick lookup
    connection_map = {}
    for conn in user_connections:
        slug = conn.get('slug')
        if slug:
            connection_map[slug] = {
                'name': conn.get('name', ''),
                'title': conn.get('title', '')
            }

    # Find matches
    results = []

    for vc_name, companies in firm_portfolio.items():
        for company_name in companies:
            if company_name not in founders_db:
                continue

            company_data = founders_db[company_name]

            # Check founders
            for founder in company_data.get('founders', []):
                slug = extract_linkedin_slug(founder.get('linkedin', ''))
                if slug and slug in connection_map:
                    results.append({
                        'vc': vc_name,
                        'company': company_name,
                        'person_role': 'Founder',
                        'person_name': founder.get('name', ''),
                        'person_linkedin': founder.get('linkedin', ''),
                        'connection_name': connection_map[slug]['name'],
                        'connection_title': connection_map[slug]['title']
                    })

            # Check CEO
            ceo = company_data.get('ceo')
            if ceo:
                slug = extract_linkedin_slug(ceo.get('linkedin', ''))
                if slug and slug in connection_map:
                    results.append({
                        'vc': vc_name,
                        'company': company_name,
                        'person_role': 'CEO',
                        'person_name': ceo.get('name', ''),
                        'person_linkedin': ceo.get('linkedin', ''),
                        'connection_name': connection_map[slug]['name'],
                        'connection_title': connection_map[slug]['title']
                    })

    return results
