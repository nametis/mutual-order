import discogs_client
import re
import time
from requests_oauthlib import OAuth1Session
from flask import current_app
from .cache_service import cache_result

class DiscogsRateLimit:
    """Rate limiting for Discogs API"""
    def __init__(self, max_calls_per_minute=25):
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
            # No app context - just print to stdout
            print("⚠️ Discogs client setup requires app context")
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.error(f"Error setting up Discogs client: {e}")
            except RuntimeError:
                print(f"Error setting up Discogs client: {e}")
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
            
            # Debug logging
            try:
                from flask import current_app
                current_app.logger.info(f"=== DEBUG LISTING {listing_id} ===")
                current_app.logger.info(f"listing.price.value: {listing.price.value}")
                current_app.logger.info(f"listing.price.currency: {listing.price.currency}")
            except RuntimeError:
                print(f"=== DEBUG LISTING {listing_id} ===")
                print(f"listing.price.value: {listing.price.value}")
                print(f"listing.price.currency: {listing.price.currency}")
            
            image_url = None
            if listing.release and listing.release.images:
                image_url = listing.release.images[0].get("uri")
            
            seller_name = "Unknown Seller"
            if hasattr(listing, 'seller') and listing.seller:
                seller_name = listing.seller.username
            
            sleeve_condition = getattr(listing, 'sleeve_condition', listing.condition)
            
            return {
                'id': str(listing.id),
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
    
    @cache_result(expire_seconds=1800)  # 30 minutes
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
                
                if page > 10:  # Safety limit
                    break
            
            return wantlist
            
        except Exception as e:
            current_app.logger.error(f"Erreur récupération wantlist: {e}")
            return []


# Global service instance
discogs_service = DiscogsService()