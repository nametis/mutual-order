import json
import re
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from flask import current_app
from models import db, WantlistItem, WantlistReference, Listing, User
from .discogs_service import discogs_service
from .cache_service import cache_result

class WantlistService:
    """Service for managing user wantlists and finding references in seller listings"""
    
    def __init__(self):
        self._initialized = False
    
    def _setup_service(self):
        """Setup service - only call within app context"""
        if self._initialized:
            return
        self._initialized = True
    
    @cache_result(expire_seconds=1800)  # 30 minutes
    def sync_user_wantlist(self, user_id, force_refresh=False):
        """Sync user's wantlist from Discogs to local database"""
        try:
            from flask import current_app
            self._setup_service()
            
            # Get user from database
            user = User.query.get(user_id)
            if not user:
                raise Exception("User not found")
            
            # Check if we need to refresh (force or last sync was more than 30 minutes ago)
            if not force_refresh:
                last_sync = db.session.query(db.func.max(WantlistItem.last_checked)).filter_by(user_id=user_id).scalar()
                if last_sync and (datetime.now(timezone.utc) - last_sync).total_seconds() < 1800:
                    current_app.logger.info(f"Wantlist for user {user_id} is up to date")
                    return self.get_user_wantlist(user_id)
            
            # Fetch wantlist from Discogs
            discogs_wantlist = discogs_service.get_user_wantlist(
                user_id, 
                user.discogs_username, 
                user.discogs_access_token, 
                user.discogs_access_secret
            )
            
            if not discogs_wantlist:
                current_app.logger.warning(f"No wantlist data found for user {user_id}")
                return []
            
            # Process and store wantlist items
            synced_items = []
            for want_data in discogs_wantlist:
                # Check if item already exists
                existing_item = WantlistItem.query.filter_by(
                    user_id=user_id,
                    discogs_want_id=str(want_data['id'])
                ).first()
                
                if existing_item:
                    # Update existing item
                    existing_item.update_from_discogs_data(want_data)
                    synced_items.append(existing_item)
                else:
                    # Create new item
                    new_item = WantlistItem(
                        user_id=user_id,
                        discogs_want_id=str(want_data['id']),
                        release_id=str(want_data['release_id']),
                        title=want_data['title'],
                        artists=json.dumps(want_data['artists']),
                        year=want_data['year'],
                        format=want_data['format'],
                        thumb_url=want_data['thumb'],
                        date_added=datetime.fromisoformat(want_data['date_added'].replace('Z', '+00:00')) if want_data.get('date_added') else None
                    )
                    db.session.add(new_item)
                    synced_items.append(new_item)
            
            db.session.commit()
            current_app.logger.info(f"Synced {len(synced_items)} wantlist items for user {user_id}")
            
            return [item.to_dict() for item in synced_items]
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error syncing wantlist for user {user_id}: {e}")
            raise Exception(f"Error syncing wantlist: {e}")
    
    def get_user_wantlist(self, user_id):
        """Get user's wantlist from local database"""
        try:
            self._setup_service()
            
            items = WantlistItem.query.filter_by(user_id=user_id).order_by(WantlistItem.date_added.desc()).all()
            return [item.to_dict() for item in items]
            
        except Exception as e:
            current_app.logger.error(f"Error getting wantlist for user {user_id}: {e}")
            return []
    
    def find_references_in_listings(self, user_id, order_id=None):
        """Find references to user's wantlist items in seller listings"""
        try:
            self._setup_service()
            
            # Get user's wantlist items
            wantlist_items = WantlistItem.query.filter_by(user_id=user_id).all()
            if not wantlist_items:
                return []
            
            # Get all active listings (optionally filtered by order)
            query = Listing.query.filter_by(status='For Sale')
            if order_id:
                query = query.filter_by(order_id=order_id)
            
            listings = query.all()
            if not listings:
                return []
            
            references = []
            
            for wantlist_item in wantlist_items:
                for listing in listings:
                    # Check if this listing matches the wantlist item
                    match_confidence = self._calculate_match_confidence(wantlist_item, listing)
                    
                    if match_confidence > 0.7:  # Threshold for considering it a match
                        # Check if reference already exists
                        existing_ref = WantlistReference.query.filter_by(
                            wantlist_item_id=wantlist_item.id,
                            listing_id=listing.id
                        ).first()
                        
                        if not existing_ref:
                            # Create new reference
                            reference = WantlistReference(
                                wantlist_item_id=wantlist_item.id,
                                listing_id=listing.id,
                                user_id=user_id,
                                match_confidence=match_confidence
                            )
                            db.session.add(reference)
                            references.append(reference)
                        else:
                            # Update existing reference confidence
                            existing_ref.match_confidence = match_confidence
                            references.append(existing_ref)
            
            db.session.commit()
            return [ref.to_dict() for ref in references]
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error finding references for user {user_id}: {e}")
            return []
    
    def _calculate_match_confidence(self, wantlist_item, listing):
        """Calculate how confident we are that a listing matches a wantlist item"""
        try:
            confidence = 0.0
            
            # Title similarity (most important)
            title_similarity = self._text_similarity(wantlist_item.title, listing.title)
            confidence += title_similarity * 0.6
            
            # Artist matching
            if wantlist_item.artists:
                artists = json.loads(wantlist_item.artists)
                if artists:
                    # Check if any artist from wantlist appears in listing title
                    artist_found = any(artist.lower() in listing.title.lower() for artist in artists)
                    if artist_found:
                        confidence += 0.3
            
            # Year matching
            if wantlist_item.year and listing.title:
                # Try to extract year from listing title
                year_match = re.search(r'\b(19|20)\d{2}\b', listing.title)
                if year_match:
                    listing_year = int(year_match.group())
                    if abs(wantlist_item.year - listing_year) <= 1:  # Within 1 year
                        confidence += 0.1
            
            return min(confidence, 1.0)  # Cap at 1.0
            
        except Exception as e:
            current_app.logger.error(f"Error calculating match confidence: {e}")
            return 0.0
    
    def _text_similarity(self, text1, text2):
        """Calculate text similarity between two strings"""
        if not text1 or not text2:
            return 0.0
        
        # Normalize text
        text1 = re.sub(r'[^\w\s]', '', text1.lower())
        text2 = re.sub(r'[^\w\s]', '', text2.lower())
        
        return SequenceMatcher(None, text1, text2).ratio()
    
    def get_wantlist_stats(self, user_id):
        """Get statistics about user's wantlist and references"""
        try:
            self._setup_service()
            
            # Count wantlist items
            wantlist_count = WantlistItem.query.filter_by(user_id=user_id).count()
            
            # Count references
            references_count = WantlistReference.query.filter_by(user_id=user_id).count()
            
            # Count unique listings with references
            unique_listings = db.session.query(WantlistReference.listing_id).filter_by(user_id=user_id).distinct().count()
            
            # Get recent references (last 7 days)
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recent_references = WantlistReference.query.filter(
                WantlistReference.user_id == user_id,
                WantlistReference.created_at >= week_ago
            ).count()
            
            return {
                'wantlist_items': wantlist_count,
                'total_references': references_count,
                'unique_listings': unique_listings,
                'recent_references': recent_references
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting wantlist stats for user {user_id}: {e}")
            return {
                'wantlist_items': 0,
                'total_references': 0,
                'unique_listings': 0,
                'recent_references': 0
            }
    
    def cleanup_old_references(self, days=30):
        """Clean up old references that are no longer valid"""
        try:
            self._setup_service()
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Find references where the listing is no longer available
            old_references = db.session.query(WantlistReference).join(Listing).filter(
                Listing.status != 'For Sale',
                WantlistReference.created_at < cutoff_date
            ).all()
            
            deleted_count = 0
            for ref in old_references:
                db.session.delete(ref)
                deleted_count += 1
            
            db.session.commit()
            current_app.logger.info(f"Cleaned up {deleted_count} old references")
            
            return deleted_count
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cleaning up old references: {e}")
            return 0


# Global service instance
wantlist_service = WantlistService()
