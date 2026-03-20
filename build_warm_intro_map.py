#!/usr/bin/env python3
"""
Build warm intro map for Matthew Millard (CapyBara Energy).

This script creates a mapping of which connections can introduce Matthew to
energy/climate VCs based on their founded companies' investor lists.

Output: warm_intro_map.json
"""

import json
from collections import defaultdict

def load_json(filepath):
    """Load JSON file."""
    with open(filepath) as f:
        return json.load(f)

def main():
    # Load data
    print("Loading data...")
    linkedin_map = load_json('linkedin_vc_map_all.json')
    vc_tags = load_json('vc_tags.json')

    # Energy-relevant tags to filter for
    energy_tags = {'energy', 'energy tech', 'clean energy', 'climate', 'green tech'}

    # Build reverse index: VC → list of (connection, company, round) tuples
    vc_to_connections = defaultdict(list)
    total_connections = 0
    connections_with_vcs = 0

    for connection_name, connection_data in linkedin_map.items():
        total_connections += 1
        has_vc_relationship = False

        for company in connection_data.get('companies_founded', []):
            company_name = company.get('name', '')

            for investor in company.get('investors', []):
                vc_name = investor.get('vc_name', '')
                round_name = investor.get('round', 'Unknown')

                if vc_name:
                    vc_to_connections[vc_name].append({
                        'connection_name': connection_name,
                        'linkedin': connection_data.get('linkedin', ''),
                        'via_company': company_name,
                        'relationship': round_name
                    })
                    has_vc_relationship = True

        if has_vc_relationship:
            connections_with_vcs += 1

    # Categorize VCs by energy relevance
    energy_vcs = {}
    other_vcs = {}

    for vc_name in sorted(vc_to_connections.keys()):
        intro_list = vc_to_connections[vc_name]

        # Get VC metadata from vc_tags if available
        vc_info = vc_tags.get(vc_name, {})
        focus_tags = vc_info.get('focus', [])
        ma_presence = vc_info.get('ma_presence', False)
        hq = vc_info.get('hq', 'Unknown')

        # Check if energy-relevant
        is_energy_relevant = any(tag.lower() in energy_tags for tag in focus_tags)

        vc_entry = {
            'tags': focus_tags if focus_tags else ['unverified'],
            'hq': hq,
            'ma_presence': ma_presence,
            'intros_available': intro_list
        }

        if is_energy_relevant:
            energy_vcs[vc_name] = vc_entry
        else:
            other_vcs[vc_name] = vc_entry

    # Sort each section: MA presence first, then alphabetically
    def sort_vcs(vc_dict):
        """Sort VCs by MA presence (descending) then name (ascending)."""
        return dict(sorted(
            vc_dict.items(),
            key=lambda x: (-x[1]['ma_presence'], x[0])
        ))

    energy_vcs = sort_vcs(energy_vcs)
    other_vcs = sort_vcs(other_vcs)

    # Count energy-relevant intros
    energy_relevant_vc_intros = len(energy_vcs)
    total_unique_vcs = len(energy_vcs) + len(other_vcs)

    # Build output
    output = {
        'summary': {
            'total_connections_analyzed': total_connections,
            'connections_with_vc_relationships': connections_with_vcs,
            'energy_relevant_vc_intros': energy_relevant_vc_intros,
            'total_unique_vcs_accessible': total_unique_vcs
        },
        'energy_vcs': energy_vcs,
        'other_vcs': other_vcs
    }

    # Write output
    with open('warm_intro_map.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Warm intro map created: warm_intro_map.json")
    print(f"\nSummary:")
    print(f"  Total connections analyzed: {total_connections}")
    print(f"  Connections with VC relationships: {connections_with_vcs}")
    print(f"  Energy/climate VCs accessible: {energy_relevant_vc_intros}")
    print(f"  Total unique VCs accessible: {total_unique_vcs}")

    # Verify key VCs
    print(f"\nKey energy VCs found:")
    for vc_name in ['Clean Energy Ventures', 'Energy Impact Partners',
                     'Breakthrough Energy Ventures', 'Lowercarbon Capital']:
        if vc_name in energy_vcs:
            intros = energy_vcs[vc_name]['intros_available']
            print(f"  ✓ {vc_name}: {len(intros)} intro path(s)")
            for intro in intros[:2]:
                print(f"      via {intro['via_company']} ({intro['connection_name']})")
        else:
            print(f"  ✗ {vc_name}: NOT FOUND")

if __name__ == '__main__':
    main()
