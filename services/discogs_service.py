import discogs_client
import re
import time
from requests_oauthlib import OAuth1Session
from flask import current_app
from .cache_service import cache_result

class DiscogsRateLimit:
    """Rate limiting for Discogs API"""
    def __init__(self, max_calls_per_minute=60):
        self.calls = 0
        self.reset_time = time.time() + 60
        self.max_calls_per_minute = max_calls_per_minute
    
    def check_limit(self):
        """Check if we can make a Discogs API call"""
        current_time = time.time()
        
        # Reset counter if minute has passed
        if current_time >= self.reset_time:
            self.calls = 0
            self.reset_time = current_time + 60
        
        # Check if we've exceeded the limit
        if self.calls >= self.max_calls_per_minute:
            wait_time = self.reset_time - current_time
            raise Exception(f"Rate limit exceeded. Wait {int(wait_time)} seconds")
        
        self.calls += 1

# Global rate limiter instance
rate_limiter = DiscogsRateLimit()

class DiscogsService:
    """Service for interacting with Discogs API"""
    
    def __init__(self):
        self.client = None
        self._initialized = False
    
    def _setup_client(self):
        """Setup Discogs client with app configuration - only call within app context"""
        if self._initialized:
            return
            
        try:
            from flask import current_app
            config = current_app.config
            
            if all([
                config.get('DISCOGS_CONSUMER_KEY'),
                config.get('DISCOGS_CONSUMER_SECRET'),
                config.get('DISCOGS_ACCESS_TOKEN'),
                config.get('DISCOGS_ACCESS_SECRET')
            ]):
                self.client = discogs_client.Client(config['USER_AGENT'])
                self.client.set_consumer_key(
                    config['DISCOGS_CONSUMER_KEY'],
                    config['DISCOGS_CONSUMER_SECRET']
                )
                self.client.set_token(
                    config['DISCOGS_ACCESS_TOKEN'],
                    config['DISCOGS_ACCESS_SECRET']
                )
                current_app.logger.info("✅ Discogs client initialized")
            else:
                current_app.logger.warning("⚠️ Discogs credentials missing")
        except RuntimeError:
            import logging
            logging.warning("⚠️ Discogs client setup requires app context")
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.error(f"Error setting up Discogs client: {e}")
            except RuntimeError:
                import logging
                logging.error(f"Error setting up Discogs client: {e}")
        finally:
            self._initialized = True
    
    def get_oauth_session(self, token=None, token_secret=None):
        """Create OAuth session for user-specific API calls"""
        try:
            from flask import current_app
            config = current_app.config
            session = OAuth1Session(
                config['DISCOGS_CONSUMER_KEY'],
                client_secret=config['DISCOGS_CONSUMER_SECRET'],
                resource_owner_key=token,
                resource_owner_secret=token_secret,
                callback_uri=config['DISCOGS_CALLBACK_URL']
            )
            
            # Add headers for currency preference
            session.headers.update({
                'Accept-Language': 'fr-FR,fr;q=0.9',
                'Accept-Currency': 'EUR'
            })
            
            return session
        except RuntimeError:
            # No app context - return basic session
            session = OAuth1Session(
                token or '',
                client_secret='',
                resource_owner_key=token,
                resource_owner_secret=token_secret
            )
            return session
    
    def extract_listing_id(self, url):
        """Extract listing ID from Discogs URL"""
        match = re.search(r"/sell/item/(\d+)", url)
        return match.group(1) if match else None
    
    @cache_result(expire_seconds=900)  # 15 minutes
    def fetch_listing_data(self, listing_id):
        """Fetch listing data from Discogs API with caching"""
        if not self._initialized:
            self._setup_client()
            
        if not self.client:
            raise Exception("Discogs client not configured")
        
        try:
            rate_limiter.check_limit()
            listing = self.client.listing(listing_id)

            image_url = None
            if listing.release and listing.release.images:
                image_url = listing.release.images[0].get("uri")
            
            seller_name = "Unknown Seller"
            if hasattr(listing, 'seller') and listing.seller:
                seller_name = listing.seller.username
            
            sleeve_condition = getattr(listing, 'sleeve_condition', listing.condition)
            
            return {
                'id': str(listing.id),
                'release_id': str(listing.release.id) if listing.release else None,
                'title': listing.release.title if listing.release else "Unknown",
                'price_value': float(listing.price.value),
                'currency': listing.price.currency,
                'media_condition': listing.condition,
                'sleeve_condition': sleeve_condition,
                'image_url': image_url,
                'seller_name': seller_name,
                'status': listing.status
            }
        except Exception as e:
            raise Exception(f"Erreur lors de la récupération des données Discogs: {e}")
    
    @cache_result(expire_seconds=900)  # 15 minutes cache
    def fetch_seller_inventory_count(self, seller_name):
        """Fetch seller's inventory count (lightweight call)"""
        if not self._initialized:
            self._setup_client()
            
        try:
            from flask import current_app
            rate_limiter.check_limit()
            
            # URL encode the seller name
            import urllib.parse
            encoded_seller_name = urllib.parse.quote(seller_name)
            
            # Get OAuth session for authenticated requests
            oauth = self.get_oauth_session(
                current_app.config.get('DISCOGS_ACCESS_TOKEN'),
                current_app.config.get('DISCOGS_ACCESS_SECRET')
            )
            
            url = f'https://api.discogs.com/users/{encoded_seller_name}/inventory'

            # Get pagination info from first page to get total count
            response = oauth.get(
                url,
                params={'page': 1, 'per_page': 1}  # Only need 1 item to get pagination info
            )

            if response.status_code == 200:
                data = response.json()
                pagination = data.get('pagination', {})
                total_items = pagination.get('items', 0)
                
                return total_items
            else:
                
                current_app.logger.error(f"Failed to get inventory count for {seller_name}: {response.status_code}")
                return 0
                
        except Exception as e:
            
            current_app.logger.error(f"Error fetching inventory count for {seller_name}: {e}")
            return 0

    def fetch_seller_info(self, seller_name):
        """Fetch seller information from Discogs API with caching"""
        if not self._initialized:
            self._setup_client()
            
        try:
            from flask import current_app
            rate_limiter.check_limit()
            
            # Get OAuth session for authenticated requests
            oauth = self.get_oauth_session(
                current_app.config.get('DISCOGS_ACCESS_TOKEN'),
                current_app.config.get('DISCOGS_ACCESS_SECRET')
            )
            
            current_app.logger.info(f"DEBUG SELLER: Making direct API call for {seller_name}")
            
            # Make direct API call to get full user data
            response = oauth.get(f'https://api.discogs.com/users/{seller_name}')
            
            if response.status_code == 200:
                user_data = response.json()
                current_app.logger.info(f"DEBUG SELLER: Full API response keys: {list(user_data.keys())}")
                
                # Look for seller rating in different possible locations
                seller_rating = None
                
                # Check various possible fields
                for field in ['seller_rating', 'marketplace_rating', 'rating', 'seller_rating_avg']:
                    if field in user_data and user_data[field] is not None:
                        seller_rating = user_data[field]
                        current_app.logger.info(f"DEBUG SELLER: Found {field}: {seller_rating}")
                        break
                
                # If still no seller rating, log all numeric fields for debugging
                if seller_rating is None:
                    numeric_fields = {k: v for k, v in user_data.items() if isinstance(v, (int, float))}
                    current_app.logger.info(f"DEBUG SELLER: All numeric fields: {numeric_fields}")
                
                return {
                    'username': seller_name,
                    'location': user_data.get('location', 'Non spécifiée') or 'Non spécifiée',
                    'rating': seller_rating
                }
            else:
                current_app.logger.error(f"DEBUG SELLER: API call failed with status {response.status_code}")
                return {'username': seller_name, 'location': 'Non spécifiée', 'rating': None}
                
        except Exception as e:
            current_app.logger.error(f"DEBUG SELLER: Exception for {seller_name}: {e}")
            return {'username': seller_name, 'location': 'Non spécifiée', 'rating': None}
    
    def get_user_info(self, access_token, access_token_secret):
        """Get user info from Discogs OAuth identity endpoint"""
        oauth = self.get_oauth_session(access_token, access_token_secret)
        response = oauth.get('https://api.discogs.com/oauth/identity')
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Erreur API Discogs: {response.status_code}")
    
    @cache_result(expire_seconds=1800)  # 30 minutes
    def get_user_wantlist(self, user_id, discogs_username, access_token, access_token_secret):
        """Get user's wantlist from Discogs"""
        try:
            oauth = self.get_oauth_session(access_token, access_token_secret)
            
            wantlist = []
            page = 1
            per_page = 100
            
            while True:
                response = oauth.get(
                    f'https://api.discogs.com/users/{discogs_username}/wants',
                    params={'page': page, 'per_page': per_page}
                )
                
                if response.status_code != 200:
                    break
                    
                data = response.json()
                wants = data.get('wants', [])
                
                for want in wants:
                    release = want.get('basic_information', {})
                    wantlist.append({
                        'id': want.get('id'),
                        'release_id': release.get('id'),
                        'title': release.get('title'),
                        'artists': [artist.get('name') for artist in release.get('artists', [])],
                        'year': release.get('year'),
                        'format': ', '.join([fmt.get('name', '') for fmt in release.get('formats', [])]),
                        'thumb': release.get('thumb', ''),
                        'date_added': want.get('date_added')
                    })
                
                if len(wants) < per_page:
                    break
                page += 1
            
            return wantlist
            
        except Exception as e:
            current_app.logger.error(f"Erreur récupération wantlist: {e}")
            return []
    
    @cache_result(expire_seconds=900)  # 15 minutes
    def fetch_seller_inventory(self, seller_name, access_token, access_token_secret):
        """Fetch seller's inventory from Discogs API with caching (full inventory)"""
        try:
            oauth = self.get_oauth_session(access_token, access_token_secret)
            
            # First, check pagination info to see if seller is too large
            response = oauth.get(
                f'https://api.discogs.com/users/{seller_name}/inventory',
                params={'page': 1, 'per_page': 100}
            )
            
            if response.status_code != 200:
                current_app.logger.error(f"Failed to get pagination info for {seller_name}: {response.status_code}")
                return []
            
            data = response.json()
            pagination = data.get('pagination', {})
            total_pages = pagination.get('pages', 1)
            total_items = pagination.get('items', 0)
            
            # Check if seller is too large (Discogs API limitation: pagination above 100 pages disabled)
            if total_pages > 100:
                current_app.logger.warning(f"Seller {seller_name} has {total_pages} pages ({total_items} items) - exceeds Discogs API limit of 100 pages")
                current_app.logger.info(f"Classifying {seller_name} as 'Large Seller' - inventory fetching disabled")
                return []
            
            inventory = []
            page = 1
            per_page = 100
            
            # Process the first page we already fetched
            listings = data.get('listings', [])
            if listings:
                for listing in listings:
                    release = listing.get('release', {})
                    inventory.append({
                        'id': str(listing.get('id')),
                        'release_id': str(release.get('id')) if release.get('id') else None,
                        'title': release.get('title', 'Unknown'),
                        'price_value': float(listing.get('price', {}).get('value', 0)),
                        'currency': listing.get('price', {}).get('currency', 'USD'),
                        'media_condition': listing.get('condition', 'Unknown'),
                        'sleeve_condition': listing.get('sleeve_condition', 'Unknown'),
                        'listing_url': f"https://www.discogs.com/sell/item/{listing.get('id')}",
                        'status': listing.get('status', 'For Sale')
                    })
            
            # Continue with remaining pages
            page = 2
            while True:
                response = oauth.get(
                    f'https://api.discogs.com/users/{seller_name}/inventory',
                    params={'page': page, 'per_page': per_page}
                )
                
                if response.status_code != 200:
                    current_app.logger.warning(f"Failed to fetch inventory page {page} for {seller_name}: {response.status_code}")
                    break
                    
                data = response.json()
                listings = data.get('listings', [])
                
                # Check if we got any listings
                if not listings:
                    current_app.logger.info(f"No more listings found at page {page} for {seller_name}")
                    break
                
                for listing in listings:
                    release = listing.get('release', {})
                    inventory.append({
                        'id': str(listing.get('id')),
                        'release_id': str(release.get('id')) if release.get('id') else None,
                        'title': release.get('title', 'Unknown'),
                        'price_value': float(listing.get('price', {}).get('value', 0)),
                        'currency': listing.get('price', {}).get('currency', 'USD'),
                        'media_condition': listing.get('condition', 'Unknown'),
                        'sleeve_condition': listing.get('sleeve_condition', 'Unknown'),
                        'listing_url': f"https://www.discogs.com/sell/item/{listing.get('id')}",
                        'status': listing.get('status', 'For Sale')
                    })
                
                # Check if we got fewer listings than expected (end of inventory)
                if len(listings) < per_page:
                    current_app.logger.info(f"Reached end of inventory at page {page} for {seller_name} (got {len(listings)} items)")
                    break
                
                page += 1
                
                # Safety check for very large inventories (prevent infinite loops)
                if page > 200:  # 200 pages = 20,000 items max
                    current_app.logger.warning(f"Reached safety limit of 200 pages for {seller_name}, stopping")
                    break
            
            current_app.logger.info(f"Fetched {len(inventory)} items from {seller_name}'s inventory")
            return inventory
            
        except Exception as e:
            current_app.logger.error(f"Error fetching seller inventory for {seller_name}: {e}")
            return []
    
    @cache_result(expire_seconds=300)  # 5 minutes cache for listing IDs
    def fetch_seller_listing_ids(self, seller_name, access_token, access_token_secret):
        """Fetch only listing IDs from seller's inventory (lightweight call)"""
        try:
            oauth = self.get_oauth_session(access_token, access_token_secret)
            
            listing_ids = []
            page = 1
            per_page = 100
            
            while True:
                response = oauth.get(
                    f'https://api.discogs.com/users/{seller_name}/inventory',
                    params={'page': page, 'per_page': per_page}
                )
                
                if response.status_code != 200:
                    current_app.logger.warning(f"Failed to fetch listing IDs page {page} for {seller_name}: {response.status_code}")
                    break
                    
                data = response.json()
                listings = data.get('listings', [])
                
                # Check if we got any listings
                if not listings:
                    current_app.logger.info(f"No more listing IDs found at page {page} for {seller_name}")
                    break
                
                # Extract only listing IDs
                for listing in listings:
                    listing_ids.append(str(listing.get('id')))
                
                # Check if we got fewer listings than expected (end of inventory)
                if len(listings) < per_page:
                    current_app.logger.info(f"Reached end of listing IDs at page {page} for {seller_name} (got {len(listings)} items)")
                    break
                
                page += 1
                
                # Safety check for very large inventories (prevent infinite loops)
                if page > 200:  # 200 pages = 20,000 items max
                    current_app.logger.warning(f"Reached safety limit of 200 pages for listing IDs for {seller_name}, stopping")
                    break
            
            current_app.logger.info(f"Fetched {len(listing_ids)} listing IDs from {seller_name}'s inventory")
            return listing_ids
            
        except Exception as e:
            current_app.logger.error(f"Error fetching listing IDs for {seller_name}: {e}")
            return []
    
    def fetch_listing_details(self, listing_ids, access_token, access_token_secret):
        """Fetch detailed information for specific listing IDs"""
        try:
            oauth = self.get_oauth_session(access_token, access_token_secret)
            detailed_listings = []
            
            # Process in batches to avoid overwhelming the API
            batch_size = 10
            for i in range(0, len(listing_ids), batch_size):
                batch = listing_ids[i:i + batch_size]
                
                for listing_id in batch:
                    try:
                        response = oauth.get(f'https://api.discogs.com/listings/{listing_id}')
                        
                        if response.status_code == 200:
                            listing = response.json()
                            release = listing.get('release', {})
                            
                            detailed_listings.append({
                                'id': str(listing.get('id')),
                                'release_id': str(release.get('id')) if release.get('id') else None,
                                'title': release.get('title', 'Unknown'),
                                'price_value': float(listing.get('price', {}).get('value', 0)),
                                'currency': listing.get('price', {}).get('currency', 'USD'),
                                'media_condition': listing.get('condition', 'Unknown'),
                                'sleeve_condition': listing.get('sleeve_condition', 'Unknown'),
                                'listing_url': f"https://www.discogs.com/sell/item/{listing.get('id')}",
                                'status': listing.get('status', 'For Sale')
                            })
                        else:
                            current_app.logger.warning(f"Failed to fetch details for listing {listing_id}: {response.status_code}")
                    
                    except Exception as e:
                        current_app.logger.error(f"Error fetching details for listing {listing_id}: {e}")
                        continue
                
                # Rate limiting between batches
                if i + batch_size < len(listing_ids):
                    time.sleep(1.0)  # 1 second delay to respect Discogs 60/min rate limit between batches
            
            current_app.logger.info(f"Fetched details for {len(detailed_listings)} listings")
            return detailed_listings
            
        except Exception as e:
            current_app.logger.error(f"Error fetching listing details: {e}")
            return []
    
    def fetch_seller_inventory_smart_incremental(self, seller_name, access_token, access_token_secret, cached_metadata=None):
        """Smart incremental fetch using sort=listed to get only new listings"""
        try:
            oauth = self.get_oauth_session(access_token, access_token_secret)
            
            # If no cached metadata, fall back to full fetch
            if not cached_metadata or not cached_metadata.get('most_recent_listing_date'):
                current_app.logger.info(f"No cached metadata for {seller_name}, falling back to full fetch")
                return self.fetch_seller_inventory(seller_name, access_token, access_token_secret)
            
            most_recent_cached = cached_metadata.get('most_recent_listing_date')
            current_app.logger.info(f"Fetching new listings for {seller_name} since {most_recent_cached}")
            
            new_listings = []
            page = 1
            per_page = 100
            total_fetched = 0
            
            while True:
                response = oauth.get(
                    f'https://api.discogs.com/users/{seller_name}/inventory',
                    params={
                        'page': page, 
                        'per_page': per_page,
                        'sort': 'listed',
                        'sort_order': 'desc'
                    }
                )
                
                if response.status_code != 200:
                    current_app.logger.warning(f"Failed to fetch smart inventory page {page} for {seller_name}: {response.status_code}")
                    break
                    
                data = response.json()
                listings = data.get('listings', [])
                
                if not listings:
                    current_app.logger.info(f"No more listings found at page {page} for {seller_name}")
                    break
                
                page_new_listings = 0
                for listing in listings:
                    listing_date = listing.get('listed', '')
                    
                    # Parse listing date for comparison
                    if listing_date and listing_date > most_recent_cached:
                        release = listing.get('release', {})
                        new_listings.append({
                            'id': str(listing.get('id')),
                            'release_id': str(release.get('id')) if release.get('id') else None,
                            'title': release.get('title', 'Unknown'),
                            'price_value': float(listing.get('price', {}).get('value', 0)),
                            'currency': listing.get('price', {}).get('currency', 'USD'),
                            'media_condition': listing.get('condition', 'Unknown'),
                            'sleeve_condition': listing.get('sleeve_condition', 'Unknown'),
                            'listing_url': f"https://www.discogs.com/sell/item/{listing.get('id')}",
                            'status': listing.get('status', 'For Sale'),
                            'listed_date': listing_date
                        })
                        page_new_listings += 1
                    else:
                        # We've reached cached data - stop fetching
                        current_app.logger.info(f"Reached cached data at page {page} for {seller_name}, stopping")
                        return new_listings, total_fetched
                
                total_fetched += len(listings)
                current_app.logger.info(f"Page {page}: {page_new_listings} new listings, {len(listings)} total")
                
                # Check if we got fewer listings than expected (end of inventory)
                if len(listings) < per_page:
                    current_app.logger.info(f"Reached end of inventory at page {page} for {seller_name}")
                    break
                
                page += 1
                
                # Safety check for very large inventories
                if page > 50:  # 50 pages = 5,000 items max for incremental
                    current_app.logger.warning(f"Reached safety limit of 50 pages for smart incremental fetch for {seller_name}")
                    break
            
            current_app.logger.info(f"Smart incremental fetch for {seller_name}: {len(new_listings)} new listings in {total_fetched} total items checked")
            return new_listings, total_fetched
            
        except Exception as e:
            current_app.logger.error(f"Error in smart incremental fetch for {seller_name}: {e}")
            return [], 0
    
    def fetch_seller_inventory_complete(self, seller_name, access_token, access_token_secret, cached_inventory):
        """Fetch complete inventory using pagination to get missing items"""
        try:
            oauth = self.get_oauth_session(access_token, access_token_secret)
            
            current_app.logger.info(f"Fetching complete inventory for {seller_name} using pagination")
            
            # First, get pagination info from page 1
            response = oauth.get(
                f'https://api.discogs.com/users/{seller_name}/inventory',
                params={'page': 1, 'per_page': 100}
            )
            
            if response.status_code != 200:
                current_app.logger.error(f"Failed to get pagination info: {response.status_code}")
                return cached_inventory if cached_inventory else [], []
            
            data = response.json()
            pagination = data.get('pagination', {})
            total_pages = pagination.get('pages', 1)
            total_items = pagination.get('items', 0)
            
            current_app.logger.info(f"Total items: {total_items}, Total pages: {total_pages}")
            
            # Check if seller is too large (Discogs API limitation: pagination above 100 pages disabled)
            if total_pages > 100:
                current_app.logger.warning(f"Seller {seller_name} has {total_pages} pages ({total_items} items) - exceeds Discogs API limit of 100 pages")
                current_app.logger.info(f"Classifying {seller_name} as 'Large Seller' - inventory fetching disabled")
                
                # Return cached inventory if available, otherwise empty with special metadata
                if cached_inventory:
                    current_app.logger.info(f"Returning cached inventory for large seller: {len(cached_inventory)} items")
                    return cached_inventory, cached_inventory[:20]
                else:
                    current_app.logger.info(f"No cached inventory for large seller {seller_name}")
                    return [], []
            
            # If we have cached data, check how many we have vs total
            if cached_inventory:
                cached_count = len(cached_inventory)
                missing_count = total_items - cached_count
                current_app.logger.info(f"Cached items: {cached_count}, Missing: {missing_count}")
                
                if missing_count <= 0:
                    current_app.logger.info("No missing items, returning cached data")
                    return cached_inventory, cached_inventory[:20]
                
                # Fetch missing items from the end pages
                return self._fetch_missing_items_from_end_pages(
                    oauth, seller_name, total_pages, cached_inventory, missing_count
                )
            else:
                # No cached data, fetch everything
                return self._fetch_all_items_via_pagination(
                    oauth, seller_name, total_pages, total_items
                )
            
        except Exception as e:
            current_app.logger.error(f"Error fetching complete inventory for {seller_name}: {e}")
            return cached_inventory if cached_inventory else [], []
    
    def _fetch_missing_items_from_end_pages(self, oauth, seller_name, total_pages, cached_inventory, missing_count):
        """Fetch missing items from the end pages where they should be located"""
        current_app.logger.info(f"Fetching missing {missing_count} items from end pages")
        
        # Get cached item IDs for deduplication
        cached_ids = set(item['id'] for item in cached_inventory)
        
        new_items = []
        per_page = 100
        
        # Calculate which pages to fetch based on missing count
        # Strategy: Try the last few pages where missing items might be located
        pages_to_fetch = []
        
        if missing_count > 0:
            # Try the last few pages to find missing items
            # Start from a few pages before the end to be safe
            start_page = max(1, total_pages - 2)  # Start from 2 pages before the end
            end_page = total_pages
            
            # Create page ranges: try last few pages individually
            for page in range(start_page, end_page + 1):
                pages_to_fetch.append((page, page))  # Single page per batch for missing items
        
        current_app.logger.info(f"Will fetch pages in batches: {pages_to_fetch}")
        
        for batch_start, batch_end in pages_to_fetch:
            current_app.logger.info(f"Fetching pages {batch_start}-{batch_end} for missing items")
            
            # Fetch this batch of pages
            for page in range(batch_start, batch_end + 1):
                try:
                    response = oauth.get(
                        f'https://api.discogs.com/users/{seller_name}/inventory',
                        params={'page': page, 'per_page': per_page}
                    )
                    
                    if response.status_code == 403:
                        current_app.logger.warning(f"Page {page} not accessible (403) - might not exist, skipping")
                        continue
                    elif response.status_code != 200:
                        current_app.logger.warning(f"Failed to fetch page {page}: {response.status_code}")
                        continue
                    
                    data = response.json()
                    listings = data.get('listings', [])
                    
                    if not listings:
                        current_app.logger.info(f"No more listings at page {page}")
                        break
                    
                    # Process listings and filter out cached items
                    for listing in listings:
                        listing_id = str(listing.get('id'))
                        if listing_id not in cached_ids:
                            release = listing.get('release', {})
                            processed_item = {
                                'id': listing_id,
                                'release_id': str(release.get('id')) if release.get('id') else None,
                                'title': release.get('title', 'Unknown'),
                                'price_value': float(listing.get('price', {}).get('value', 0)),
                                'currency': listing.get('price', {}).get('currency', 'USD'),
                                'media_condition': listing.get('condition', 'Unknown'),
                                'sleeve_condition': listing.get('sleeve_condition', 'Unknown'),
                                'listing_url': f"https://www.discogs.com/sell/item/{listing_id}",
                                'status': listing.get('status', 'For Sale'),
                                'listed_date': listing.get('listed', '')
                            }
                            new_items.append(processed_item)
                    
                    # Check if we got fewer listings than expected (end of inventory)
                    if len(listings) < per_page:
                        current_app.logger.info(f"Reached end of inventory at page {page} (got {len(listings)} items)")
                        break
                    
                    # Stop if we found enough missing items
                    if len(new_items) >= missing_count:
                        current_app.logger.info(f"Found {len(new_items)} missing items, stopping")
                        break
                    
                    time.sleep(1.0)  # 1 second delay to respect Discogs 60/min rate limit
                    
                except Exception as e:
                    current_app.logger.warning(f"Error fetching page {page}: {e}")
                    continue
            
            # Stop if we found enough missing items
            if len(new_items) >= missing_count:
                break
        
        # If we didn't find any new items and we're still missing items, try a different approach
        if len(new_items) == 0 and missing_count > 0:
            current_app.logger.info("No new items found, trying to refetch last page with larger per_page")
            
            # Try to refetch the last page with a larger per_page to get more items
            try:
                response = oauth.get(
                    f'https://api.discogs.com/users/{seller_name}/inventory',
                    params={'page': total_pages, 'per_page': 200}  # Try larger page size
                )
                
                if response.status_code == 200:
                    data = response.json()
                    listings = data.get('listings', [])
                    
                    # Process any additional listings we might have missed
                    for listing in listings:
                        listing_id = str(listing.get('id'))
                        if listing_id not in cached_ids:
                            release = listing.get('release', {})
                            processed_item = {
                                'id': listing_id,
                                'release_id': str(release.get('id')) if release.get('id') else None,
                                'title': release.get('title', 'Unknown'),
                                'price_value': float(listing.get('price', {}).get('value', 0)),
                                'currency': listing.get('price', {}).get('currency', 'USD'),
                                'media_condition': listing.get('condition', 'Unknown'),
                                'sleeve_condition': listing.get('sleeve_condition', 'Unknown'),
                                'listing_url': f"https://www.discogs.com/sell/item/{listing_id}",
                                'status': listing.get('status', 'For Sale'),
                                'listed_date': listing.get('listed', '')
                            }
                            new_items.append(processed_item)
                    
                    current_app.logger.info(f"Found {len(new_items)} additional items with larger per_page")
                    
            except Exception as e:
                current_app.logger.warning(f"Error trying larger per_page: {e}")
        
        # Combine cached items with new items
        complete_inventory = cached_inventory + new_items
        
        current_app.logger.info(f"Found {len(new_items)} new items, total: {len(complete_inventory)}")
        
        return complete_inventory, complete_inventory[:20]
    
    def _fetch_all_items_via_pagination(self, oauth, seller_name, total_pages, total_items):
        """Fetch all items via pagination using efficient batching (fallback when no cache)"""
        current_app.logger.info(f"Fetching all {total_items} items via pagination with efficient batching")
        
        all_items = []
        failed_pages = []
        per_page = 100
        
        # Create efficient page ranges: 50 pages per batch
        pages_to_fetch = []
        for batch_start in range(1, total_pages + 1, 50):
            batch_end = min(batch_start + 49, total_pages)
            pages_to_fetch.append((batch_start, batch_end))
        
        current_app.logger.info(f"Will fetch pages in batches: {pages_to_fetch}")
        
        for batch_start, batch_end in pages_to_fetch:
            current_app.logger.info(f"Fetching pages {batch_start}-{batch_end}/{total_pages}")
            
            for page in range(batch_start, batch_end + 1):
                try:
                    response = oauth.get(
                        f'https://api.discogs.com/users/{seller_name}/inventory',
                        params={'page': page, 'per_page': per_page}
                    )
                    
                    if response.status_code == 502:
                        current_app.logger.warning(f"502 error on page {page}, retrying...")
                        time.sleep(2)
                        continue
                    elif response.status_code != 200:
                        current_app.logger.warning(f"Failed page {page}: {response.status_code}")
                        failed_pages.append(page)
                        continue
                    
                    data = response.json()
                    listings = data.get('listings', [])
                    
                    for listing in listings:
                        release = listing.get('release', {})
                        processed_item = {
                            'id': str(listing.get('id')),
                            'release_id': str(release.get('id')) if release.get('id') else None,
                            'title': release.get('title', 'Unknown'),
                            'price_value': float(listing.get('price', {}).get('value', 0)),
                            'currency': listing.get('price', {}).get('currency', 'USD'),
                            'media_condition': listing.get('condition', 'Unknown'),
                            'sleeve_condition': listing.get('sleeve_condition', 'Unknown'),
                            'listing_url': f"https://www.discogs.com/sell/item/{listing.get('id')}",
                            'status': listing.get('status', 'For Sale'),
                            'listed_date': listing.get('listed', '')
                        }
                        all_items.append(processed_item)
                    
                    time.sleep(1.0)  # 1 second delay to respect Discogs 60/min rate limit
                    
                except Exception as e:
                    current_app.logger.warning(f"Error on page {page}: {e}")
                    failed_pages.append(page)
                    continue
        
        current_app.logger.info(f"Fetched {len(all_items)} items, failed pages: {failed_pages}")
        
        return all_items, all_items[:20]

# Global service instance
discogs_service = DiscogsService()