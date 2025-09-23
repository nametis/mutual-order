from datetime import datetime, timezone
from . import db

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_name = db.Column(db.String(100), nullable=False, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='building', index=True)
    status_changed_at = db.Column(db.DateTime, nullable=True)
    max_amount = db.Column(db.Float, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    payment_timing = db.Column(db.String(50), default="avant la commande")
    seller_shop_url = db.Column(db.Text, nullable=True)
    direct_url = db.Column(db.Text, nullable=True)
    shipping_cost = db.Column(db.Float, default=0.0)
    taxes = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    user_location = db.Column(db.String(200), nullable=True)
    paypal_link = db.Column(db.Text, nullable=True)
    
    # Relationships
    listings = db.relationship('Listing', backref='order', cascade='all, delete-orphan', lazy='dynamic')
    validations = db.relationship('UserValidation', backref='order', cascade='all, delete-orphan')
    chat_messages = db.relationship('OrderChat', backref='order', cascade='all, delete-orphan')
    
    @property
    def total_price(self):
        """Total price of all available listings"""
        from .listing import Listing
        
        total = db.session.query(db.func.sum(Listing.price_value)).filter(
            Listing.order_id == self.id,
            Listing.status == 'For Sale'
        ).scalar()
        
        return float(total or 0.0)
    
    @property
    def total_with_fees(self):
        """Total price including shipping and taxes"""
        return self.total_price + self.shipping_cost + self.taxes
    
    @property
    def total_with_discount(self):
        """Total after applying discount"""
        return max(0, self.total_with_fees - (self.discount or 0))
    
    @property
    def currency(self):
        """Get currency from first available listing"""
        from .listing import Listing
        
        listing = db.session.query(Listing).filter(
            Listing.order_id == self.id,
            Listing.status == 'For Sale'
        ).first()
        
        return listing.currency if listing else "EUR"
    
    @property
    def participants(self):
        """Get all users who have listings in this order"""
        from .user import User
        from .listing import Listing
        
        # Get unique user IDs who have listings in this order
        user_ids = db.session.query(Listing.user_id).filter(
            Listing.order_id == self.id
        ).distinct().all()
        
        # Extract IDs from tuples
        user_ids = [uid[0] for uid in user_ids if uid[0] is not None]
        
        if not user_ids:
            return []
        
        return User.query.filter(User.id.in_(user_ids)).all()
    
    @property
    def participants_count(self):
        """Count unique participants"""
        from .listing import Listing
        
        return db.session.query(Listing.user_id).filter(
            Listing.order_id == self.id
        ).distinct().count()
    
    def get_user_summary(self, user_id):
        """Calculate order summary for a specific user"""
        from .listing import Listing
        
        user_listings = db.session.query(Listing).filter(
            Listing.status == 'For Sale', 
            Listing.user_id == user_id,
            Listing.order_id == self.id
        ).all()
        
        if not user_listings:
            return {
                'listings_count': 0,
                'subtotal': 0.0,
                'fees_share': 0.0,
                'discount_share': 0.0,
                'total': 0.0
            }
        
        subtotal = sum(listing.price_value for listing in user_listings)
        total_items = db.session.query(Listing).filter(
            Listing.status == 'For Sale',
            Listing.order_id == self.id
        ).count()
        
        # Proportional fee calculation
        if total_items > 0:
            total_fees = self.shipping_cost + self.taxes
            fees_share = (total_fees * len(user_listings)) / total_items
            discount_share = (self.discount * len(user_listings)) / total_items if self.discount else 0.0
        else:
            fees_share = 0.0
            discount_share = 0.0
        
        return {
            'listings_count': len(user_listings),
            'subtotal': round(subtotal, 2),
            'fees_share': round(fees_share, 2),
            'discount_share': round(discount_share, 2),
            'total': round(subtotal + fees_share - discount_share, 2)
        }
    
    def get_all_participants_summary(self):
        """Summary for all participants"""
        participants_summary = {}
        
        for participant in self.participants:
            participants_summary[participant.id] = {
                'user': {
                    'id': participant.id,
                    'username': participant.username,
                    'is_creator': participant.id == self.creator_id
                },
                'summary': self.get_user_summary(participant.id)
            }
        
        return participants_summary
    
    def to_dict(self, include_listings=False, current_user_id=None):
        """Convert order to dictionary for API responses"""
        data = {
            'id': self.id,
            'seller_name': self.seller_name,
            'status': self.status,
            'creator_id': self.creator_id,
            'creator': {'id': self.creator_id, 'username': self.creator.username},
            'total_price': self.total_price,
            'shipping_cost': self.shipping_cost,
            'taxes': self.taxes,
            'discount': self.discount,
            'total_with_fees': self.total_with_fees,
            'total_with_discount': self.total_with_discount,
            'max_amount': self.max_amount,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'payment_timing': self.payment_timing,
            'created_at': self.created_at.isoformat(),
            'user_location': self.user_location,
            'seller_shop_url': self.seller_shop_url,
            'direct_url': self.direct_url,
            'participants_count': self.participants_count,
            'participants': [
                {
                    'id': p.id, 
                    'username': p.username, 
                    'is_creator': p.id == self.creator_id
                } for p in self.participants
            ]
        }
        
        if include_listings:
            from .listing import Listing
            
            available_listings = db.session.query(Listing).filter(
                Listing.order_id == self.id,
                Listing.status == 'For Sale'
            ).all()
            
            data['available_count'] = len(available_listings)
            data['listings'] = [listing.to_dict() for listing in available_listings]
        
        if current_user_id:
            data['current_user_summary'] = self.get_user_summary(current_user_id)
        
        return data
    
    def __repr__(self):
        return f'<Order {self.id}: {self.seller_name}>'


class UserValidation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    validated = db.Column(db.Boolean, default=False)
    validated_at = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'order_id', name='unique_user_order_validation'),
    )
    
    def __repr__(self):
        return f'<UserValidation user:{self.user_id} order:{self.order_id} validated:{self.validated}>'