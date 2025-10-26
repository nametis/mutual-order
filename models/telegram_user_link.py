from datetime import datetime, timezone
from . import db

class TelegramUserLink(db.Model):
    """Link Mutual Order user accounts to Telegram users"""
    __tablename__ = 'telegram_user_links'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    telegram_user_id = db.Column(db.String(100), nullable=False, unique=True)  # Telegram user ID
    telegram_username = db.Column(db.String(100), nullable=True)
    telegram_first_name = db.Column(db.String(100), nullable=True)
    telegram_last_name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = db.Column(db.DateTime, nullable=True)
    
    # Relationship
    user = db.relationship('User', backref='telegram_link', uselist=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'telegram_user_id': self.telegram_user_id,
            'telegram_username': self.telegram_username,
            'telegram_first_name': self.telegram_first_name,
            'telegram_last_name': self.telegram_last_name,
            'display_name': self.get_display_name(),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }
    
    def get_display_name(self):
        """Get display name for the Telegram user"""
        if self.telegram_first_name or self.telegram_last_name:
            parts = [p for p in [self.telegram_first_name, self.telegram_last_name] if p]
            return ' '.join(parts)
        elif self.telegram_username:
            return f'@{self.telegram_username}'
        else:
            return f'User {self.telegram_user_id}'
