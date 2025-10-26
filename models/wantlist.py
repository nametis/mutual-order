from datetime import datetime, timezone
from . import db

class WantlistItem(db.Model):
    """Model for storing user wantlist items from Discogs"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    discogs_want_id = db.Column(db.String(20), nullable=False, index=True)  # Discogs want ID
    release_id = db.Column(db.String(20), nullable=False, index=True)  # Discogs release ID
    title = db.Column(db.String(500), nullable=False)
    artists = db.Column(db.Text)  # JSON string of artists
    year = db.Column(db.Integer)
    format = db.Column(db.String(200))
    thumb_url = db.Column(db.Text)
    date_added = db.Column(db.DateTime)  # When added to wantlist on Discogs
    last_checked = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref='wantlist_items')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'discogs_want_id', name='unique_want_per_user'),
        db.Index('idx_user_release', 'user_id', 'release_id'),
    )
    
    def to_dict(self):
        """Convert wantlist item to dictionary for API responses"""
        import json
        return {
            'id': self.id,
            'discogs_want_id': self.discogs_want_id,
            'release_id': self.release_id,
            'title': self.title,
            'artists': json.loads(self.artists) if self.artists else [],
            'year': self.year,
            'format': self.format,
            'thumb_url': self.thumb_url,
            'date_added': self.date_added.isoformat() if self.date_added else None,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user_id': self.user_id
        }
    
    def update_from_discogs_data(self, discogs_data):
        """Update wantlist item from Discogs API data"""
        import json
        self.title = discogs_data.get('title', self.title)
        self.artists = json.dumps(discogs_data.get('artists', []))
        self.year = discogs_data.get('year', self.year)
        self.format = discogs_data.get('format', self.format)
        self.thumb_url = discogs_data.get('thumb', self.thumb_url)
        self.date_added = discogs_data.get('date_added', self.date_added)
        self.last_checked = datetime.now(timezone.utc)
    
    def __repr__(self):
        return f'<WantlistItem {self.id}: {self.title[:50]}...>'

class WantlistReference(db.Model):
    """Model for storing references between wantlist items and seller listings"""
    id = db.Column(db.Integer, primary_key=True)
    wantlist_item_id = db.Column(db.Integer, db.ForeignKey('wantlist_item.id'), nullable=False, index=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)  # User who owns the wantlist
    match_confidence = db.Column(db.Float, default=1.0)  # How confident we are this is a match
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    wantlist_item = db.relationship('WantlistItem', backref='references')
    listing = db.relationship('Listing', backref='wantlist_references')
    user = db.relationship('User', backref='wantlist_references')
    
    __table_args__ = (
        db.UniqueConstraint('wantlist_item_id', 'listing_id', name='unique_wantlist_listing_ref'),
        db.Index('idx_user_wantlist_refs', 'user_id', 'created_at'),
    )
    
    def to_dict(self):
        """Convert reference to dictionary for API responses"""
        return {
            'id': self.id,
            'wantlist_item_id': self.wantlist_item_id,
            'listing_id': self.listing_id,
            'user_id': self.user_id,
            'match_confidence': self.match_confidence,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'wantlist_item': self.wantlist_item.to_dict() if self.wantlist_item else None,
            'listing': self.listing.to_dict() if self.listing else None
        }
    
    def __repr__(self):
        return f'<WantlistReference {self.id}: wantlist_item={self.wantlist_item_id}, listing={self.listing_id}>'
