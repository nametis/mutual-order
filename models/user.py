from datetime import datetime, timezone
from . import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    discogs_username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    discogs_access_token = db.Column(db.String(200), nullable=False)
    discogs_access_secret = db.Column(db.String(200), nullable=False)
    mutual_order_username = db.Column(db.String(80), unique=True, nullable=True, index=True)
    profile_completed = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # New profile fields for settings
    default_location = db.Column(db.String(200), nullable=True)
    default_paypal_link = db.Column(db.Text, nullable=True)
    
    # Relationships
    created_orders = db.relationship('Order', backref='creator', lazy='dynamic')
    user_listings = db.relationship('Listing', backref='user', lazy='dynamic')
    validations = db.relationship('UserValidation', backref='user', lazy='dynamic')
    chat_messages = db.relationship('OrderChat', backref='user', lazy='dynamic')
    favorite_sellers = db.relationship('FavoriteSeller', back_populates='user', lazy='dynamic')
    friends = db.relationship('Friend', foreign_keys='Friend.user_id', back_populates='user', lazy='dynamic')
    friend_of = db.relationship('Friend', foreign_keys='Friend.friend_user_id', back_populates='friend_user', lazy='dynamic')
    sent_friend_requests = db.relationship('FriendRequest', foreign_keys='FriendRequest.requester_id', back_populates='requester', lazy='dynamic')
    received_friend_requests = db.relationship('FriendRequest', foreign_keys='FriendRequest.requested_id', back_populates='requested', lazy='dynamic')
    
    # Propriété pour compatibilité avec le code existant
    @property
    def username(self):
        return self.mutual_order_username if self.mutual_order_username else self.discogs_username
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    # Flask-Login compatibility
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
    
    def to_dict(self):
        """Convert user to dictionary for API responses"""
        return {
            'id': self.id,
            'username': '@' + self.username if self.mutual_order_username else self.discogs_username,
            'discogs_username': self.discogs_username,
            'is_admin': self.is_admin,
            'profile_completed': self.profile_completed,
            'created_at': self.created_at.isoformat(),
            'default_location': self.default_location,
            'default_paypal_link': self.default_paypal_link
        }