from datetime import datetime, timezone
from . import db

class OrderChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self, current_user_id=None, timezone_func=None):
        """Convert chat message to dictionary for API responses"""
        created_time = self.created_at
        if timezone_func:
            created_time = timezone_func(self.created_at)
            timestamp = created_time.strftime('%d/%m %H:%M')
        else:
            timestamp = self.created_at.isoformat()
        
        return {
            'id': self.id,
            'username': self.user.username,
            'content': self.message,
            'timestamp': timestamp,
            'is_own': self.user_id == current_user_id if current_user_id else False,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<OrderChat {self.id}: {self.user.username} in order {self.order_id}>'


class ChatReadStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id', ondelete='CASCADE'), nullable=False)
    last_read_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User')
    order = db.relationship('Order')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'order_id', name='unique_user_order_read_status'),
    )
    
    def mark_read(self):
        """Update last read timestamp to now"""
        self.last_read_at = datetime.now(timezone.utc)
    
    def get_unread_count(self):
        """Get count of unread messages for this user in this order"""
        return OrderChat.query.filter(
            OrderChat.order_id == self.order_id,
            OrderChat.created_at > self.last_read_at,
            OrderChat.user_id != self.user_id  # Don't count own messages
        ).count()
    
    def __repr__(self):
        return f'<ChatReadStatus user:{self.user_id} order:{self.order_id}>'