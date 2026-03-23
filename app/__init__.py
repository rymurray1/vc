from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(config=None):
    """Application factory."""
    app = Flask(__name__)

    # Configuration
    if config is None:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SECRET_KEY'] = 'dev-key-change-in-production'
    else:
        app.config.update(config)

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    from app.routes import main
    app.register_blueprint(main.bp)

    from app.routes import admin
    app.register_blueprint(admin.bp)

    # Create database tables
    with app.app_context():
        db.create_all()

    return app
