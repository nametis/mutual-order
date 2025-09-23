from datetime import datetime, timezone
from . import db

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    discogs_id = db.Column(db.String(20), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    price_value = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(5), nullable=False)
    media_condition = db.Column(db.String(50), nullable=False)
    sleeve_condition = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.Text)
    listing_url = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='For Sale', index=True)
    last_checked = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    
    __table_args__ = (
        db.UniqueConstraint('discogs_id', 'order_id', name='unique_listing_per_order'),
    )
    
    def to_dict(self):
        """Convert listing to dictionary for API responses"""
        return {
            'id': self.id,
            'discogs_id': self.discogs_id,
            'title': self.title,
            'price_value': self.price_value,
            'currency': self.currency,
            'media_condition': self.media_condition,
            'sleeve_condition': self.sleeve_condition,
            'image_url': self.image_url,
            'listing_url': self.listing_url,
            'status': self.status,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'added_at': self.added_at.isoformat() if self.added_at else None,
            'user_id': self.user_id,
            'username': self.user.username,
            'order_id': self.order_id
        }
    
    def update_from_discogs_data(self, discogs_data):
        """Update listing from Discogs API data"""
        self.title = discogs_data.get('title', self.title)
        self.price_value = discogs_data.get('price_value', self.price_value)
        self.currency = discogs_data.get('currency', self.currency)
        self.media_condition = discogs_data.get('media_condition', self.media_condition)
        self.sleeve_condition = discogs_data.get('sleeve_condition', self.sleeve_condition)
        self.image_url = discogs_data.get('image_url', self.image_url)
        self.status = discogs_data.get('status', 'For Sale')
        self.last_checked = datetime.now(timezone.utc)
    
    @property
    def is_available(self):
        """Check if listing is still for sale"""
        return self.status == 'For Sale'
    
    def __repr__(self):
        return f'<Listing {self.id}: {self.title[:50]}...>'