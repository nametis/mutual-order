from datetime import datetime, timezone
from . import db

class UserPayment(db.Model):
    """Track payment status for each user in an order"""
    __tablename__ = 'user_payment'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    amount_due = db.Column(db.Float, nullable=False)  # Total amount user needs to pay
    amount_paid = db.Column(db.Float, default=0.0)  # Amount actually paid
    is_paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    payment_reference = db.Column(db.String(200), nullable=True)  # PayPal transaction ID, etc.
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    order = db.relationship('Order', backref='payments')
    user = db.relationship('User')
    
    __table_args__ = (
        db.UniqueConstraint('order_id', 'user_id', name='unique_order_user_payment'),
    )
    
    def mark_as_paid(self, amount=None, payment_reference=None, notes=None):
        """Mark payment as completed"""
        self.is_paid = True
        self.paid_at = datetime.now(timezone.utc)
        if amount is not None:
            self.amount_paid = amount
        if payment_reference:
            self.payment_reference = payment_reference
        if notes:
            self.notes = notes
        self.updated_at = datetime.now(timezone.utc)
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'order_id': self.order_id,
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'mutual_order_username': self.user.mutual_order_username
            },
            'amount_due': self.amount_due,
            'amount_paid': self.amount_paid,
            'is_paid': self.is_paid,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'payment_reference': self.payment_reference,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<UserPayment order:{self.order_id} user:{self.user_id} paid:{self.is_paid}>'

