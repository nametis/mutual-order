from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from . import db

class Friend(db.Model):
    __tablename__ = 'friend'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Unique constraint to prevent duplicate friendships
    __table_args__ = (UniqueConstraint('user_id', 'friend_user_id', name='unique_friendship'),)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="friends")
    friend_user = relationship("User", foreign_keys=[friend_user_id], back_populates="friend_of")
    
    def to_dict(self):
        return {
            'id': self.id,
            'friend_user_id': self.friend_user_id,
            'username': f"@{self.friend_user.mutual_order_username}" if self.friend_user and self.friend_user.mutual_order_username else (f"@{self.friend_user.discogs_username}" if self.friend_user else None),
            'mutual_order_username': self.friend_user.mutual_order_username if self.friend_user else None,
            'created_at': self.created_at.isoformat()
        }

