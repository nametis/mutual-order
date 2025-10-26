from datetime import datetime, timezone
from . import db

class TelegramLinkToken(db.Model):
    """Model for one-time Telegram account linking tokens"""
    __tablename__ = 'telegram_link_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), nullable=False, unique=True)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=True)  # Optional expiry
    
    # Relationship
    user = db.relationship('User', backref='telegram_link_tokens', uselist=False)
