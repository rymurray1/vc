#!/usr/bin/env python3
"""Entry point for the Flask app."""

from app import create_app, db

if __name__ == '__main__':
    app = create_app()

    with app.app_context():
        db.create_all()

    print("Starting VC Intro Paths on http://localhost:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)
