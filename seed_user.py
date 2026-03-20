#!/usr/bin/env python
"""
Seed user account with password hash.
Run once to create Matt Millard's account.

Usage:
    python seed_user.py
"""

import sys
import os
from getpass import getpass

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import User


def seed_user():
    """Create Matt Millard's user account."""
    app = create_app()

    with app.app_context():
        # Check if user already exists
        existing = User.query.filter_by(username='matt.millard').first()
        if existing:
            print("✗ User 'matt.millard' already exists")
            return

        # Prompt for password
        password = getpass("Enter password for matt.millard: ")
        if not password:
            print("✗ Password cannot be empty")
            return

        confirm = getpass("Confirm password: ")
        if password != confirm:
            print("✗ Passwords do not match")
            return

        # Create user
        user = User(username='matt.millard')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        print(f"✓ Created user 'matt.millard' with sync token: {user.sync_token}")


if __name__ == '__main__':
    seed_user()
