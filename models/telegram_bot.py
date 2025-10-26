from datetime import datetime, timezone
from . import db

class TelegramInteraction(db.Model):
    """Log all bot interactions for monitoring and analytics"""
    __tablename__ = 'telegram_interactions'
    
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(50), nullable=False, index=True)  # Telegram chat ID
    user_id = db.Column(db.String(100))  # Telegram user ID
    username = db.Column(db.String(100))  # Telegram username
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    message_text = db.Column(db.Text)  # What the user sent
    command = db.Column(db.String(50))  # Command used (e.g., /start, /link)
    response_sent = db.Column(db.Text)  # What the bot replied
    interaction_type = db.Column(db.String(20), index=True)  # 'command', 'message', 'callback', 'auto_linking'
    linked_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Linked Mutual Order user
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationship to linked user
    linked_user = db.relationship('User', backref='telegram_interactions', uselist=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'user_id': self.user_id,
            'username': self.username,
            'display_name': self.get_display_name(),
            'message_text': self.message_text,
            'command': self.command,
            'response_sent': self.response_sent,
            'interaction_type': self.interaction_type,
            'linked_user_id': self.linked_user_id,
            'linked_user_username': self.linked_user.username if self.linked_user else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def get_display_name(self):
        """Get display name for the Telegram user"""
        if self.first_name or self.last_name:
            parts = [p for p in [self.first_name, self.last_name] if p]
            return ' '.join(parts)
        elif self.username:
            return f'@{self.username}'
        else:
            return f'User {self.user_id}'

class TelegramBotCommand(db.Model):
    """Model for storing Telegram bot command responses"""
    __tablename__ = 'telegram_bot_commands'
    
    id = db.Column(db.Integer, primary_key=True)
    command = db.Column(db.String(50), nullable=False, unique=True)  # e.g., "/start", "/help"
    response = db.Column(db.Text, nullable=False)  # The response message
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'command': self.command,
            'response': self.response,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class TelegramChannel(db.Model):
    """Model for storing Telegram channel configurations"""
    __tablename__ = 'telegram_channels'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Display name
    chat_id = db.Column(db.String(50), nullable=False, unique=True)  # Channel chat ID
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'chat_id': self.chat_id,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
