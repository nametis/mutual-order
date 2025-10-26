from flask import session, current_app
from models import User, db
from .discogs_service import discogs_service

class AuthService:
    """Authentication service for managing user authentication"""
    
    @staticmethod
    def test_user_tokens(user):
        """Test if user's Discogs tokens are still valid"""
        if not user or not user.discogs_access_token or not user.discogs_access_secret:
            return False
        
        try:
            from .discogs_service import discogs_service
            test_session = discogs_service.get_oauth_session(
                user.discogs_access_token, 
                user.discogs_access_secret
            )
            
            # Quick test of the tokens
            response = test_session.get('https://api.discogs.com/oauth/identity')
            if response.status_code == 200:
                # Verify the username matches
                user_info = response.json()
                return user_info.get('username') == user.discogs_username
            
            return False
            
        except Exception:
            return False

    @staticmethod
    def get_current_user():
        """Get the currently logged in user"""
        user_id = session.get('user_id')
        if user_id:
            return User.query.get(user_id)
        return None
    
    @staticmethod
    def is_authenticated():
        """Check if user is authenticated"""
        return 'user_id' in session
    
    @staticmethod
    def login_user(user):
        """Log in a user by setting session"""
        from datetime import datetime, timezone
        
        session['user_id'] = user.id
        session.permanent = True
        
        # Update last login timestamp
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()
    
    @staticmethod
    def logout_user():
        """Log out the current user"""
        session.pop('user_id', None)
    
    @staticmethod
    def create_or_update_user_from_discogs(discogs_username, access_token, access_token_secret):
        """Create or update user from Discogs OAuth data"""
        # Check if user exists
        user = User.query.filter_by(discogs_username=discogs_username).first()
        
        # Admin status should be managed via database column
        # Initial admin can be set via direct database query or admin interface
        # For new users, default to non-admin
        is_admin = False
        if user and user.is_admin:
            # Preserve existing admin status
            is_admin = True
        
        if not user:
            # Create new user
            user = User(
                discogs_username=discogs_username,
                discogs_access_token=access_token,
                discogs_access_secret=access_token_secret,
                is_admin=is_admin,
                profile_completed=False
            )
            db.session.add(user)
            is_new_user = True
        else:
            # Update existing user - refresh tokens and admin status
            user.discogs_access_token = access_token
            user.discogs_access_secret = access_token_secret
            if user.is_admin != is_admin:
                user.is_admin = is_admin
            is_new_user = False
        
        try:
            db.session.commit()
            return user, is_new_user
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to create/update user: {e}")
    
    @staticmethod
    def complete_user_profile(user, mutual_order_username, city):
        """Complete user profile setup"""
        from models.user import CITY_CHOICES
        
        # Validation
        if not mutual_order_username or len(mutual_order_username.strip()) < 2:
            raise ValueError("Username must be at least 2 characters")
        
        if len(mutual_order_username) > 30:
            raise ValueError("Username cannot exceed 30 characters")
        
        if not city or city not in CITY_CHOICES:
            raise ValueError("Please select a valid city")
        
        # Check for forbidden names
        forbidden_names = ['admin', 'api', 'www', 'support', 'help', 'discogs', 'mutual', 'order']
        if mutual_order_username.lower() in forbidden_names:
            raise ValueError("This username is reserved")
        
        # Check if username is already taken
        existing_user = User.query.filter_by(mutual_order_username=mutual_order_username).first()
        if existing_user and existing_user.id != user.id:
            raise ValueError("This username is already taken")
        
        # Update user
        user.mutual_order_username = mutual_order_username.strip()
        user.city = city
        user.profile_completed = True
        
        try:
            db.session.commit()
            return user
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to complete profile: {e}")
    
    @staticmethod
    def check_username_availability(username, current_user_id=None):
        """Check if a username is available"""
        if not username or len(username.strip()) < 2:
            return False, "Username must be at least 2 characters"
        
        if len(username) > 30:
            return False, "Username cannot exceed 30 characters"
        
        # Check forbidden names
        forbidden_names = ['admin', 'api', 'www', 'support', 'help', 'discogs', 'mutual', 'order']
        if username.lower() in forbidden_names:
            return False, "This username is reserved"
        
        # Check availability
        existing_user = User.query.filter_by(mutual_order_username=username).first()
        if existing_user and existing_user.id != current_user_id:
            return False, "This username is already taken"
        
        return True, "Username is available"
    
    @staticmethod
    def start_discogs_oauth():
        """Start Discogs OAuth flow"""
        config = current_app.config
        
        if not all([config.get('DISCOGS_CONSUMER_KEY'), config.get('DISCOGS_CONSUMER_SECRET')]):
            raise Exception("Discogs OAuth configuration missing")
        
        try:
            oauth = discogs_service.get_oauth_session()
            
            # Get request token
            fetch_response = oauth.fetch_request_token(config['DISCOGS_REQUEST_TOKEN_URL'])
            request_token = fetch_response.get('oauth_token')
            request_token_secret = fetch_response.get('oauth_token_secret')
            
            # Store temporary tokens in session
            session['oauth_token'] = request_token
            session['oauth_token_secret'] = request_token_secret
            
            # Generate authorization URL
            authorization_url = oauth.authorization_url(config['DISCOGS_AUTHORIZE_URL'])
            return authorization_url
            
        except Exception as e:
            raise Exception(f"OAuth start failed: {e}")
    
    @staticmethod
    def complete_discogs_oauth(oauth_token, oauth_verifier):
        """Complete Discogs OAuth flow"""
        config = current_app.config
        
        # Validate tokens
        request_token = session.get('oauth_token')
        request_token_secret = session.get('oauth_token_secret')
        
        if not request_token or request_token != oauth_token:
            raise Exception("Invalid OAuth token")
        
        try:
            # Exchange for access tokens
            oauth = discogs_service.get_oauth_session(request_token, request_token_secret)
            oauth_tokens = oauth.fetch_access_token(
                config['DISCOGS_ACCESS_TOKEN_URL'],
                verifier=oauth_verifier
            )
            
            access_token = oauth_tokens.get('oauth_token')
            access_token_secret = oauth_tokens.get('oauth_token_secret')
            
            # Get user info
            user_info = discogs_service.get_user_info(access_token, access_token_secret)
            discogs_username = user_info.get('username')
            
            if not discogs_username:
                raise Exception("Unable to get user information from Discogs")
            
            # Create or update user
            user, is_new_user = AuthService.create_or_update_user_from_discogs(
                discogs_username, access_token, access_token_secret
            )
            
            # Clean up session
            session.pop('oauth_token', None)
            session.pop('oauth_token_secret', None)
            
            return user, is_new_user
            
        except Exception as e:
            # Clean up session on error
            session.pop('oauth_token', None)
            session.pop('oauth_token_secret', None)
            raise Exception(f"OAuth completion failed: {e}")

# Global auth service instance
auth_service = AuthService()