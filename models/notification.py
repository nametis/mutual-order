from . import db
from datetime import datetime, timezone
from sqlalchemy import Index

class Notification(db.Model):
    __tablename__ = 'notification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True, index=True)
    
    # Notification content
    content = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False, index=True)  # 'order_created', 'status_changed', 'disc_added', 'manual'
    
    # Status
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    # Optional: who triggered the notification (for friend notifications)
    triggered_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='notifications')
    order = db.relationship('Order', backref='notifications')
    triggered_by_user = db.relationship('User', foreign_keys=[triggered_by_user_id])
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_unread', 'user_id', 'is_read'),
        Index('idx_user_created', 'user_id', 'created_at'),
        Index('idx_type_created', 'notification_type', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'order_id': self.order_id,
            'content': self.content,
            'notification_type': self.notification_type,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat(),
            'triggered_by_user_id': self.triggered_by_user_id,
            'triggered_by_username': self.triggered_by_user.username if self.triggered_by_user else None,
            'order_seller_name': self.order.seller_name if self.order else None
        }
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.content[:50]}...>'
