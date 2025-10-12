"""
Service for matching user wantlist with available listings from sellers
"""
from flask import current_app
from .discogs_service import discogs_service
from .cache_service import cache_service, cache_result
from models import Order, Listing, User
from sqlalchemy import and_, or_
from datetime import datetime, timedelta, timezone
import json
import hashlib

class WantlistMatchingService:
    """Service for matching user wantlist with seller listings"""
    
    def __init__(self):
        self.discogs_service = discogs_service
        self.inventory_cache_duration = 3600  # 1 hour for regular sellers
        self.large_seller_cache_duration = 7200  # 2 hours for large sellers (10k+ items)
    
    def get_wantlist_matches_for_user(self, user_id, bypass_cache=False):
        """Get wantlist matches for a specific user across all registered sellers' inventories"""
        try:
            # Check if we have a cached result for this user (unless bypassing cache)
            if not bypass_cache:
                cache_key = f"wantlist_matches_full_{user_id}"
                cached_result = cache_service.get(cache_key)
                if cached_result:
                    current_app.logger.info(f"✅ CACHE HIT for full wantlist matches (user {user_id})")
                    return json.loads(cached_result)
            
            # Get user's Discogs credentials
            user = User.query.get(user_id)
            if not user or not user.discogs_access_token or not user.discogs_access_secret:
                return {
                    'error': 'User not authenticated with Discogs',
                    'matches': []
                }
            
            # Get user's wantlist
            wantlist = self.discogs_service.get_user_wantlist(
                user_id, 
                user.discogs_username, 
                user.discogs_access_token, 
                user.discogs_access_secret
            )
            
            if not wantlist:
                return {
                    'error': 'No wantlist found or error fetching wantlist',
                    'matches': []
                }
            
            # Get all registered sellers (from orders and favorite sellers)
            registered_sellers = self.get_all_registered_sellers()
            
            if not registered_sellers:
                return {
                    'user_id': user_id,
                    'username': user.username,
                    'wantlist_count': len(wantlist),
                    'sellers_checked': 0,
                    'matches': [],
                    'message': 'No registered sellers found'
                }
            
            matches = []
            processed_sellers = set()  # Prevent duplicate processing
            
            for seller_name in registered_sellers:
                if seller_name in processed_sellers:
                    continue
                    
                processed_sellers.add(seller_name)
                
                # Check if seller is too large for API (skip if >100 pages)
                try:
                    oauth = self.discogs_service.get_oauth_session(
                        user.discogs_access_token, user.discogs_access_secret
                    )
                    response = oauth.get(
                        f'https://api.discogs.com/users/{seller_name}/inventory',
                        params={'page': 1, 'per_page': 100}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        pagination = data.get('pagination', {})
                        total_pages = pagination.get('pages', 0)
                        total_items = pagination.get('items', 0)
                        
                        if total_pages > 100:
                            current_app.logger.info(f"Skipping {seller_name} - Large Seller ({total_pages} pages, {total_items} items)")
                            continue
                    else:
                        current_app.logger.warning(f"Could not check {seller_name} - API error {response.status_code}")
                        continue
                        
                except Exception as e:
                    current_app.logger.warning(f"Could not check {seller_name} - {e}")
                    continue
                
                # Process seller inventory
                seller_matches = self._find_matches_for_seller_name(seller_name, wantlist, user, bypass_cache)
                if seller_matches['total_matches'] > 0:
                    matches.append(seller_matches)
            
            result = {
                'user_id': user_id,
                'username': user.username,
                'wantlist_count': len(wantlist),
                'sellers_checked': len(processed_sellers),
                'registered_sellers': registered_sellers,
                'matches': matches
            }
            
            # Cache the full result for 10 minutes (unless bypassing cache)
            if not bypass_cache:
                cache_key = f"wantlist_matches_full_{user_id}"
                cache_service.set(cache_key, json.dumps(result), expire_seconds=600)
                current_app.logger.info(f"💾 Cached full wantlist matches for user {user_id}")
            
            return result
            
        except Exception as e:
            current_app.logger.error(f"Error getting wantlist matches: {e}")
            return {
                'error': str(e),
                'matches': []
            }
    
    def _find_matches_for_seller_name(self, seller_name, wantlist, user, bypass_cache=False):
        """Find wantlist matches for a seller's entire inventory by seller name"""
        try:
            current_app.logger.info(f"Checking seller {seller_name} inventory for wantlist matches")
            
            # Get seller's inventory (cached or fresh)
            seller_inventory, metadata = self._get_incremental_seller_inventory(
                seller_name,
                user.id,
                user.discogs_access_token,
                user.discogs_access_secret,
                bypass_cache
            )
            
            if not seller_inventory:
                current_app.logger.warning(f"No inventory found for seller {seller_name}")
                return {
                    'seller_name': seller_name,
                    'total_matches': 0,
                    'inventory_count': 0,
                    'matches': [],
                    'cache_info': {
                        'is_cached': metadata is not None,
                        'is_large_seller': metadata.get('is_large_seller', False) if metadata else False,
                        'last_updated': metadata.get('last_updated') if metadata else None
                    }
                }
            
            current_app.logger.info(f"Found {len(seller_inventory)} items in {seller_name}'s inventory")
            
            # Match inventory against wantlist with optimized algorithm
            matches = []
            total_matches = 0
            
            # Create a set of wantlist release IDs for fast lookup
            wantlist_release_ids = set()
            for wantlist_item in wantlist:
                release_id = wantlist_item.get('release_id')
                if release_id:
                    wantlist_release_ids.add(str(release_id))
            
            # Process inventory items
            for item in seller_inventory:
                item_release_id = str(item.get('release_id', ''))
                
                # Fast path: exact release ID match
                if item_release_id and item_release_id in wantlist_release_ids:
                    # Find the matching wantlist item
                    for wantlist_item in wantlist:
                        if str(wantlist_item.get('release_id', '')) == item_release_id:
                            matches.append({
                                'listing_id': item.get('id'),
                                'release_id': item.get('release_id'),
                                'title': item.get('title'),
                                'artist': item.get('artist', 'Unknown'),
                                'price_value': item.get('price_value'),
                                'currency': item.get('currency'),
                                'media_condition': item.get('media_condition'),
                                'sleeve_condition': item.get('sleeve_condition'),
                                'listing_url': item.get('listing_url'),
                                'status': item.get('status'),
                                'wantlist_item': {
                                    'id': wantlist_item.get('id'),
                                    'title': wantlist_item.get('title'),
                                    'artist': wantlist_item.get('artist')
                                }
                            })
                            total_matches += 1
                            break
                else:
                    # Slow path: fuzzy matching only if no release ID match
                    for wantlist_item in wantlist:
                        if self._is_match(item, wantlist_item):
                            matches.append({
                                'listing_id': item.get('id'),
                                'release_id': item.get('release_id'),
                                'title': item.get('title'),
                                'artist': item.get('artist', 'Unknown'),
                                'price_value': item.get('price_value'),
                                'currency': item.get('currency'),
                                'media_condition': item.get('media_condition'),
                                'sleeve_condition': item.get('sleeve_condition'),
                                'listing_url': item.get('listing_url'),
                                'status': item.get('status'),
                                'wantlist_item': {
                                    'id': wantlist_item.get('id'),
                                    'title': wantlist_item.get('title'),
                                    'artist': wantlist_item.get('artist')
                                }
                            })
                            total_matches += 1
                            break  # Found a match, move to next inventory item
            
            current_app.logger.info(f"Seller {seller_name}: {total_matches} matches out of {len(seller_inventory)} inventory items")
            
            return {
                'seller_name': seller_name,
                'total_matches': total_matches,
                'inventory_count': len(seller_inventory),
                'matches': matches,
                'cache_info': {
                    'is_cached': metadata is not None,
                    'is_large_seller': metadata.get('is_large_seller', False) if metadata else False,
                    'last_updated': metadata.get('last_updated') if metadata else None
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error finding matches for seller {seller_name}: {e}")
            return {
                'seller_name': seller_name,
                'total_matches': 0,
                'inventory_count': 0,
                'matches': [],
                'error': str(e)
            }
    
    def _find_matches_for_seller_inventory(self, order, wantlist, user, bypass_cache=False):
        """Find wantlist matches for a seller's entire inventory"""
        try:
            current_app.logger.info(f"Checking seller {order.seller_name} inventory for wantlist matches")
            
            # Get seller's inventory (cached or fresh)
            seller_inventory, metadata = self._get_incremental_seller_inventory(
                order.seller_name,
                user.id,
                user.discogs_access_token,
                user.discogs_access_secret,
                bypass_cache
            )
            
            if not seller_inventory:
                current_app.logger.warning(f"No inventory found for seller {order.seller_name}")
                return {
                    'order_id': order.id,
                    'order_title': f"Commande {order.seller_name}",
                    'seller_name': order.seller_name,
                    'order_status': order.status,
                    'total_matches': 0,
                    'inventory_count': 0,
                    'matches': []
                }
            
            current_app.logger.info(f"Found {len(seller_inventory)} items in {order.seller_name}'s inventory")
            
            # Match inventory against wantlist
            matches = []
            total_matches = 0
            
            # Create a set of wantlist release IDs for efficient lookup
            wantlist_release_ids = {str(item.get('release_id')) for item in wantlist if item.get('release_id')}
            
            for inventory_item in seller_inventory:
                release_id = str(inventory_item.get('release_id', ''))
                if release_id and release_id in wantlist_release_ids:
                    # Find the matching wantlist item
                    for want_item in wantlist:
                        if str(want_item.get('release_id')) == release_id:
                            matches.append({
                                'listing_id': inventory_item.get('id'),
                                'listing_title': inventory_item.get('title'),
                                'listing_price': inventory_item.get('price_value'),
                                'listing_currency': inventory_item.get('currency'),
                                'listing_condition': f"{inventory_item.get('media_condition')} / {inventory_item.get('sleeve_condition')}",
                                'listing_url': inventory_item.get('listing_url'),
                                'wantlist_item': {
                                    'id': want_item.get('id'),
                                    'title': want_item.get('title'),
                                    'artists': want_item.get('artists', []),
                                    'year': want_item.get('year'),
                                    'format': want_item.get('format'),
                                    'thumb': want_item.get('thumb'),
                                    'date_added': want_item.get('date_added')
                                },
                                'match_confidence': 'exact'
                            })
                            total_matches += 1
                            current_app.logger.info(f"Match found: {inventory_item.get('title')} (release_id: {release_id})")
                            break
            
            current_app.logger.info(f"Seller {order.seller_name}: {total_matches} matches out of {len(seller_inventory)} inventory items")
            return {
                'order_id': order.id,
                'order_title': f"Commande {order.seller_name}",
                'seller_name': order.seller_name,
                'order_status': order.status,
                'total_matches': total_matches,
                'inventory_count': len(seller_inventory),
                'matches': matches,
                'cache_info': {
                    'is_cached': metadata is not None,
                    'is_large_seller': metadata.get('is_large_seller', False) if metadata else False,
                    'last_updated': metadata.get('last_updated') if metadata else None
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error finding matches for seller {order.seller_name}: {e}")
            return {
                'order_id': order.id,
                'order_title': f"Commande {order.seller_name}",
                'seller_name': order.seller_name,
                'total_matches': 0,
                'inventory_count': 0,
                'matches': []
            }
    
    def _match_listing_with_wantlist(self, listing, wantlist):
        """Match a single listing with wantlist items using release ID"""
        matches = []
        
        # Skip if listing doesn't have a release_id
        if not listing.release_id:
            current_app.logger.warning(f"Listing {listing.id} has no release_id, skipping")
            return matches
        
        # Create a set of wantlist release IDs for efficient lookup
        wantlist_release_ids = {str(want_item.get('release_id')) for want_item in wantlist if want_item.get('release_id')}
        
        # Check if this listing's release ID is in the wantlist
        if str(listing.release_id) in wantlist_release_ids:
            # Find the matching wantlist item
            for want_item in wantlist:
                if str(want_item.get('release_id')) == str(listing.release_id):
                    matches.append({
                        'listing_id': listing.id,
                        'listing_title': listing.title,
                        'listing_price': listing.price_value,
                        'listing_currency': listing.currency,
                        'listing_condition': f"{listing.media_condition} / {listing.sleeve_condition}",
                        'wantlist_item': {
                            'id': want_item.get('id'),
                            'title': want_item.get('title'),
                            'artists': want_item.get('artists', []),
                            'year': want_item.get('year'),
                            'format': want_item.get('format'),
                            'thumb': want_item.get('thumb'),
                            'date_added': want_item.get('date_added')
                        },
                        'match_confidence': 'exact'  # Perfect match by release ID
                    })
                    current_app.logger.info(f"Exact match found: {listing.title} (release_id: {listing.release_id})")
                    break
        
        return matches
    
    def _is_similar_title(self, title1, title2):
        """Check if two titles are similar"""
        # Remove common words and special characters
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        
        def clean_title(title):
            # Remove special characters and split into words
            import re
            words = re.findall(r'\b\w+\b', title.lower())
            return [word for word in words if word not in common_words]
        
        words1 = clean_title(title1)
        words2 = clean_title(title2)
        
        if not words1 or not words2:
            return False
        
        # Check if any significant words match
        matches = sum(1 for word in words1 if word in words2)
        similarity = matches / max(len(words1), len(words2))
        
        # Also check for exact substring matches (for cases like "LP" vs "12" LP")
        if len(title1) > 3 and len(title2) > 3:
            if title1 in title2 or title2 in title1:
                return True
        
        return similarity >= 0.4  # Lowered to 40% similarity threshold
    
    def _is_similar_artist(self, artist1, artist2):
        """Check if two artist names are similar"""
        # Simple similarity check
        if artist1 == artist2:
            return True
        
        # Check if one contains the other
        if artist1 in artist2 or artist2 in artist1:
            return True
        
        # Check word overlap
        words1 = set(artist1.split())
        words2 = set(artist2.split())
        
        if not words1 or not words2:
            return False
        
        overlap = len(words1.intersection(words2))
        similarity = overlap / max(len(words1), len(words2))
        
        return similarity >= 0.5  # 50% similarity threshold
    
    def _is_similar_title(self, title1, title2):
        """Check if two titles are similar using fuzzy matching"""
        if not title1 or not title2:
            return False
        
        # Normalize titles
        title1 = title1.lower().strip()
        title2 = title2.lower().strip()
        
        # Exact match
        if title1 == title2:
            return True
        
        # Check if one is contained in the other (for variations)
        if title1 in title2 or title2 in title1:
            return True
        
        # Check word overlap
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 or not words2:
            return False
        
        overlap = len(words1.intersection(words2))
        similarity = overlap / max(len(words1), len(words2))
        
        return similarity >= 0.7  # 70% similarity threshold for titles
    
    def _extract_artist_from_title(self, title):
        """Try to extract artist name from listing title (common pattern: 'Artist - Title')"""
        import re
        
        # Common separators used in Discogs listings
        separators = [' - ', ' – ', ' — ', ' | ', ' / ']
        
        for sep in separators:
            if sep in title:
                parts = title.split(sep, 1)
                if len(parts) == 2:
                    artist_part = parts[0].strip()
                    # Basic validation: artist should be shorter than title part
                    title_part = parts[1].strip()
                    if len(artist_part) < len(title_part) and len(artist_part) > 0:
                        return artist_part.lower()
        
        # If no separator found, try to extract first few words as artist
        words = title.split()
        if len(words) >= 2:
            # Take first 1-3 words as potential artist name
            for i in range(1, min(4, len(words))):
                potential_artist = ' '.join(words[:i]).lower()
                if len(potential_artist) < len(title) * 0.7:  # Artist shouldn't be too long
                    return potential_artist
        
        return None
    
    def _get_seller_inventory_cache_key(self, seller_name, user_id):
        """Generate cache key for seller inventory"""
        return f"seller_inventory:{seller_name}:{user_id}"
    
    def _get_seller_inventory_metadata_key(self, seller_name):
        """Generate cache key for seller inventory metadata"""
        return f"seller_metadata:{seller_name}"
    
    def _is_large_seller(self, inventory_count):
        """Check if seller has large inventory (10k+ items)"""
        return inventory_count >= 10000
    
    def _is_seller_too_large_for_api(self, total_pages):
        """Check if seller exceeds Discogs API pagination limit (100 pages)"""
        return total_pages > 100
    
    def _is_match(self, inventory_item, wantlist_item):
        """Check if an inventory item matches a wantlist item"""
        try:
            # First try exact release ID match
            inventory_release_id = str(inventory_item.get('release_id', ''))
            wantlist_release_id = str(wantlist_item.get('release_id', ''))
            
            if inventory_release_id and wantlist_release_id and inventory_release_id == wantlist_release_id:
                return True
            
            # If no release IDs, try title and artist matching
            inventory_title = inventory_item.get('title', '').lower().strip()
            inventory_artist = inventory_item.get('artist', '').lower().strip()
            wantlist_title = wantlist_item.get('title', '').lower().strip()
            wantlist_artist = wantlist_item.get('artist', '').lower().strip()
            
            # Check if titles are similar
            if inventory_title and wantlist_title:
                if self._is_similar_title(inventory_title, wantlist_title):
                    # If artists match or are similar, it's a match
                    if not inventory_artist or not wantlist_artist or self._is_similar_artist(inventory_artist, wantlist_artist):
                        return True
            
            return False
            
        except Exception as e:
            current_app.logger.warning(f"Error in _is_match: {e}")
            return False
    
    def _get_cached_seller_inventory(self, seller_name, user_id):
        """Get cached seller inventory if available and not expired"""
        try:
            cache_key = self._get_seller_inventory_cache_key(seller_name, user_id)
            metadata_key = self._get_seller_inventory_metadata_key(seller_name)
            
            current_app.logger.info(f"🔍 Checking cache for {seller_name} - cache_key: {cache_key}, metadata_key: {metadata_key}")
            
            # Check metadata first
            metadata = cache_service.get(metadata_key)
            if not metadata:
                current_app.logger.info(f"❌ No metadata found for {seller_name}")
                return None, None
            
            metadata = json.loads(metadata)
            cache_duration = self.large_seller_cache_duration if self._is_large_seller(metadata.get('count', 0)) else self.inventory_cache_duration
            
            # Check if cache is still valid
            cached_at = datetime.fromisoformat(metadata['cached_at'])
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            
            # Ensure both datetimes are timezone-aware for comparison
            now = datetime.now(timezone.utc)
            if now - cached_at > timedelta(seconds=cache_duration):
                return None, None
            
            # Get cached inventory
            cached_inventory = cache_service.get(cache_key)
            if cached_inventory:
                return json.loads(cached_inventory), metadata
            
            return None, None
            
        except Exception as e:
            current_app.logger.error(f"Error getting cached inventory for {seller_name}: {e}")
            return None, None
    
    def _cache_seller_inventory(self, seller_name, user_id, inventory, metadata):
        """Cache seller inventory and metadata"""
        try:
            cache_key = self._get_seller_inventory_cache_key(seller_name, user_id)
            metadata_key = self._get_seller_inventory_metadata_key(seller_name)
            
            # Cache inventory data
            cache_service.set(cache_key, json.dumps(inventory), expire_seconds=86400)  # 24 hours
            
            # Cache metadata
            cache_service.set(metadata_key, json.dumps(metadata), expire_seconds=86400)  # 24 hours
            
        except Exception as e:
            current_app.logger.error(f"Error caching inventory for {seller_name}: {e}")
    
    def _get_incremental_seller_inventory(self, seller_name, user_id, access_token, access_secret, bypass_cache=False):
        """Get seller inventory with incremental updates - only fetch new/updated listings"""
        try:
            # If bypass_cache is True, skip cache check and force fresh fetch
            if bypass_cache:
                current_app.logger.info(f"Bypassing cache for {seller_name}, fetching fresh inventory")
                inventory = self.discogs_service.fetch_seller_inventory(seller_name, access_token, access_secret)
                
                if not inventory:
                    return None, None
                
                # Find most recent listing date
                most_recent_date = None
                for item in inventory:
                    if 'listed_date' in item and item['listed_date']:
                        if not most_recent_date or item['listed_date'] > most_recent_date:
                            most_recent_date = item['listed_date']
                
                # Create metadata
                metadata = {
                    'seller_name': seller_name,
                    'count': len(inventory),
                    'cached_at': datetime.now(timezone.utc).isoformat(),
                    'last_updated': datetime.now(timezone.utc).isoformat(),
                    'is_large_seller': self._is_large_seller(len(inventory)),
                    'listing_ids': [item['id'] for item in inventory],
                    'most_recent_listing_date': most_recent_date
                }
                
                # Cache the results
                self._cache_seller_inventory(seller_name, user_id, inventory, metadata)
                return inventory, metadata
            
            # First check if we have cached data
            cached_inventory, metadata = self._get_cached_seller_inventory(seller_name, user_id)
            
            if not cached_inventory or not metadata:
                # No cache - do full fetch
                current_app.logger.info(f"🔍 CACHE MISS for {seller_name} - fetching full inventory")
                inventory = self.discogs_service.fetch_seller_inventory(seller_name, access_token, access_secret)
                
                if not inventory:
                    return None, None
                
                # Find most recent listing date
                most_recent_date = None
                for item in inventory:
                    if 'listed_date' in item and item['listed_date']:
                        if not most_recent_date or item['listed_date'] > most_recent_date:
                            most_recent_date = item['listed_date']
                
                # Create metadata
                metadata = {
                    'seller_name': seller_name,
                    'count': len(inventory),
                    'cached_at': datetime.now(timezone.utc).isoformat(),
                    'last_updated': datetime.now(timezone.utc).isoformat(),
                    'is_large_seller': self._is_large_seller(len(inventory)),
                    'listing_ids': [item['id'] for item in inventory],
                    'most_recent_listing_date': most_recent_date
                }
                
                # Cache the results
                self._cache_seller_inventory(seller_name, user_id, inventory, metadata)
                return inventory, metadata
            
            # Check if cache is still fresh (within 1 hour for regular sellers, 2 hours for large)
            cache_duration = self.large_seller_cache_duration if metadata.get('is_large_seller', False) else self.inventory_cache_duration
            cached_at = datetime.fromisoformat(metadata['cached_at'])
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            
            # Ensure both datetimes are timezone-aware for comparison
            now = datetime.now(timezone.utc)
            if now - cached_at <= timedelta(seconds=cache_duration):
                current_app.logger.info(f"✅ CACHE HIT for {seller_name} ({len(cached_inventory)} items) - using cached data")
                return cached_inventory, metadata
            
            # Cache is stale - use smart incremental approach
            current_app.logger.info(f"Cache stale for {seller_name}, using smart incremental fetch")
            
            # Use smart incremental fetch (sorted by most recent)
            new_listings, total_checked = self.discogs_service.fetch_seller_inventory_smart_incremental(
                seller_name, access_token, access_secret, metadata
            )
            
            if not new_listings:
                # No new listings - update cache timestamp and return cached data
                current_app.logger.info(f"No new listings found for {seller_name}, updating cache timestamp")
                metadata['cached_at'] = datetime.now(timezone.utc).isoformat()
                metadata['last_updated'] = datetime.now(timezone.utc).isoformat()
                self._cache_seller_inventory(seller_name, user_id, cached_inventory, metadata)
                return cached_inventory, metadata
            
            # New listings found - merge with cached data
            current_app.logger.info(f"Found {len(new_listings)} new listings for {seller_name} (checked {total_checked} items)")
            
            # Merge new listings with cached inventory
            updated_inventory = cached_inventory + new_listings
            
            # Find new most recent listing date
            most_recent_date = metadata.get('most_recent_listing_date')
            for item in new_listings:
                if 'listed_date' in item and item['listed_date']:
                    if not most_recent_date or item['listed_date'] > most_recent_date:
                        most_recent_date = item['listed_date']
            
            # Update metadata
            metadata.update({
                'count': len(updated_inventory),
                'cached_at': datetime.now(timezone.utc).isoformat(),
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'is_large_seller': self._is_large_seller(len(updated_inventory)),
                'listing_ids': [item['id'] for item in updated_inventory],
                'most_recent_listing_date': most_recent_date
            })
            
            # Cache the updated results
            self._cache_seller_inventory(seller_name, user_id, updated_inventory, metadata)
            
            return updated_inventory, metadata
            
        except Exception as e:
            current_app.logger.error(f"Error getting incremental inventory for {seller_name}: {e}")
            return None, None
    
    def force_refresh_seller_inventory(self, seller_name, user_id, access_token, access_secret):
        """Force refresh seller inventory, bypassing cache"""
        try:
            current_app.logger.info(f"Force refreshing inventory for {seller_name}")
            
            # Clear existing cache
            cache_key = self._get_seller_inventory_cache_key(seller_name, user_id)
            metadata_key = self._get_seller_inventory_metadata_key(seller_name)
            cache_service.delete(cache_key)
            cache_service.delete(metadata_key)
            
            # Fetch fresh inventory (no 5k limit)
            inventory = self.discogs_service.fetch_seller_inventory(seller_name, access_token, access_secret)
            
            if not inventory:
                return None, None
            
            # Find most recent listing date
            most_recent_date = None
            for item in inventory:
                if 'listed_date' in item and item['listed_date']:
                    if not most_recent_date or item['listed_date'] > most_recent_date:
                        most_recent_date = item['listed_date']
            
            # Create metadata with listing IDs and most recent date
            metadata = {
                'seller_name': seller_name,
                'count': len(inventory),
                'cached_at': datetime.now(timezone.utc).isoformat(),
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'is_large_seller': self._is_large_seller(len(inventory)),
                'listing_ids': [item['id'] for item in inventory],
                'most_recent_listing_date': most_recent_date
            }
            
            # Cache the results
            self._cache_seller_inventory(seller_name, user_id, inventory, metadata)
            
            return inventory, metadata
            
        except Exception as e:
            current_app.logger.error(f"Error force refreshing inventory for {seller_name}: {e}")
            return None, None
    
    def get_stale_sellers(self, hours_threshold=24):
        """Get list of sellers with stale cache data"""
        try:
            # This would need to be implemented based on your cache backend
            # For now, return empty list
            return []
        except Exception as e:
            current_app.logger.error(f"Error getting stale sellers: {e}")
            return []
    
    def background_refresh_seller(self, seller_name, user_id, access_token, access_secret):
        """Background refresh for a specific seller (can be called from a job queue)"""
        try:
            current_app.logger.info(f"Background refresh for {seller_name}")
            
            # Check if we need to refresh
            cached_inventory, metadata = self._get_cached_seller_inventory(seller_name, user_id)
            
            if not metadata:
                # No cache, do full refresh
                return self.force_refresh_seller_inventory(seller_name, user_id, access_token, access_secret)
            
            # Check if cache is stale
            cache_duration = self.large_seller_cache_duration if metadata.get('is_large_seller', False) else self.inventory_cache_duration
            cached_at = datetime.fromisoformat(metadata['cached_at'])
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            
            # Ensure both datetimes are timezone-aware for comparison
            now = datetime.now(timezone.utc)
            if now - cached_at > timedelta(seconds=cache_duration):
                return self.force_refresh_seller_inventory(seller_name, user_id, access_token, access_secret)
            
            # Cache is still fresh
            return cached_inventory, metadata
            
        except Exception as e:
            current_app.logger.error(f"Error in background refresh for {seller_name}: {e}")
            return None, None
    
    def get_all_registered_sellers(self):
        """Get all unique sellers from orders and favorite sellers with caching"""
        try:
            # Check cache first (5 minute cache)
            cache_key = "registered_sellers_list"
            cached_sellers = cache_service.get(cache_key)
            if cached_sellers:
                sellers = json.loads(cached_sellers)
                current_app.logger.info(f"✅ CACHE HIT for registered sellers ({len(sellers)} sellers)")
                return sellers
            
            from models.order import Order
            from models.favorite_seller import FavoriteSeller
            from models import db
            
            # Get sellers from orders
            order_sellers = db.session.query(Order.seller_name).distinct().all()
            order_seller_names = [seller[0] for seller in order_sellers if seller[0]]
            
            # Get sellers from favorite sellers
            favorite_sellers = db.session.query(FavoriteSeller.seller_name).distinct().all()
            favorite_seller_names = [seller[0] for seller in favorite_sellers if seller[0]]
            
            # Combine and deduplicate
            all_sellers = list(set(order_seller_names + favorite_seller_names))
            
            # Cache the result for 5 minutes
            cache_service.set(cache_key, json.dumps(all_sellers), expire_seconds=300)
            
            current_app.logger.info(f"Found {len(all_sellers)} registered sellers: {all_sellers}")
            return all_sellers
            
        except Exception as e:
            current_app.logger.error(f"Error getting registered sellers: {e}")
            return []
    
    def refresh_all_registered_sellers(self, user_id, access_token, access_secret):
        """Refresh inventory for all registered sellers"""
        try:
            current_app.logger.info("🔄 Starting refresh for all registered sellers")
            
            sellers = self.get_all_registered_sellers()
            if not sellers:
                current_app.logger.info("No registered sellers found")
                return
            
            refreshed_count = 0
            large_sellers = []
            
            for seller_name in sellers:
                try:
                    current_app.logger.info(f"Processing seller: {seller_name}")
                    
                    # Check if seller is too large for API
                    # We'll check this during the actual fetch
                    inventory, metadata = self.force_refresh_seller_inventory(
                        seller_name, user_id, access_token, access_secret
                    )
                    
                    if inventory is not None:
                        if len(inventory) == 0 and metadata and metadata.get('is_large_seller', False):
                            large_sellers.append(seller_name)
                            current_app.logger.info(f"✅ {seller_name} classified as Large Seller (API limit exceeded)")
                        else:
                            refreshed_count += 1
                            current_app.logger.info(f"✅ Refreshed {seller_name}: {len(inventory)} items")
                    else:
                        current_app.logger.warning(f"❌ Failed to refresh {seller_name}")
                    
                    # Rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    current_app.logger.error(f"Error processing seller {seller_name}: {e}")
                    continue
            
            current_app.logger.info(f"🎉 Refresh complete: {refreshed_count} sellers refreshed, {len(large_sellers)} large sellers")
            if large_sellers:
                current_app.logger.info(f"Large sellers (API limit exceeded): {large_sellers}")
            
        except Exception as e:
            current_app.logger.error(f"Error in refresh_all_registered_sellers: {e}")

# Global service instance
wantlist_matching_service = WantlistMatchingService()

