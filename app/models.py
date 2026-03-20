from datetime import datetime
import uuid
from app import db
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    """User model."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    sync_token = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    connections = db.relationship('Connection', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        """Hash and set user password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Connection(db.Model):
    """LinkedIn connection stored for a user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    name = db.Column(db.String(256), nullable=False)
    title = db.Column(db.String(256))
    linkedin_url = db.Column(db.String(512), nullable=False)
    slug = db.Column(db.String(256), index=True)  # Normalized LinkedIn slug
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'slug', name='uq_user_connection_slug'),)

    def __repr__(self):
        return f'<Connection {self.name}>'
