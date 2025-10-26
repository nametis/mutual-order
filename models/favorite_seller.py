from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from . import db

class FavoriteSeller(db.Model):
    __tablename__ = 'favorite_seller'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_name = db.Column(db.String(255), nullable=False)
    shop_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship
    user = relationship("User", back_populates="favorite_sellers")
    
    def to_dict(self):
        return {
            'id': self.id,
            'seller_name': self.seller_name,
            'shop_url': self.shop_url,
            'created_at': self.created_at.isoformat()
        }

