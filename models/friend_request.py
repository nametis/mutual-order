from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from . import db

class FriendRequest(db.Model):
    __tablename__ = 'friend_request'
    
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    requested_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, declined
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)
    
    # Unique constraint to prevent duplicate requests
    __table_args__ = (UniqueConstraint('requester_id', 'requested_id', name='unique_friend_request'),)
    
    # Relationships
    requester = relationship("User", foreign_keys=[requester_id], back_populates="sent_friend_requests")
    requested = relationship("User", foreign_keys=[requested_id], back_populates="received_friend_requests")
    
    def to_dict(self):
        return {
            'id': self.id,
            'requester_id': self.requester_id,
            'requested_id': self.requested_id,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'requester': {
                'id': self.requester.id,
                'username': f"@{self.requester.mutual_order_username}" if self.requester.mutual_order_username else f"@{self.requester.discogs_username}",
                'mutual_order_username': self.requester.mutual_order_username,
                'discogs_username': self.requester.discogs_username
            } if self.requester else None
        }
