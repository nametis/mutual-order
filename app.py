import os
from flask import Flask, current_app
from config import config
from models import db
from routes import register_blueprints
from services import cache_service, discogs_service
from utils import register_template_helpers

def create_app(config_name=None):
    """Application factory function
    
    Args:
        config_name (str): Configuration name to use (development, production, testing)
        
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    
    # Determine config
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    initialize_extensions(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register template helpers
    register_template_helpers(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Add security headers
    register_security_headers(app)
    
    # Initialize services
    with app.app_context():
        initialize_services(app)
    
    return app

def initialize_extensions(app):
    """Initialize Flask extensions"""
    # Initialize database
    db.init_app(app)
    
    # Create tables if they don't exist
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database tables created/verified")
        except Exception as e:
            app.logger.error(f"Error creating database tables: {e}")

def initialize_services(app):
    """Initialize application services"""
    try:
        from services import cache_service, discogs_service
        
        # Initialize services within app context
        cache_service._setup_redis()
        discogs_service._setup_client()
        
        app.logger.info("Services initialized successfully")
        
    except Exception as e:
        app.logger.error(f"Error initializing services: {e}")
        # Don't fail startup if services can't initialize
        pass

def register_error_handlers(app):
    """Register error handlers for the application"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template, request, jsonify
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        from flask import render_template, request, jsonify
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Access forbidden'}), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template, request, jsonify
        
        # Log the error
        app.logger.error(f'Internal server error: {error}')
        
        # Rollback database session to avoid issues
        db.session.rollback()
        
        if request.is_json or request.path.startswith('/api/'):
            if app.debug:
                return jsonify({'error': str(error)}), 500
            else:
                return jsonify({'error': 'Internal server error'}), 500
        
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(429)
    def rate_limit_error(error):
        from flask import request, jsonify
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
        return "Rate limit exceeded. Please try again later.", 429

def register_security_headers(app):
    """Register security headers for all responses"""
    
    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Only add HSTS in production with HTTPS
        if not app.debug and 'https' in app.config.get('PREFERRED_URL_SCHEME', ''):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response

def register_cli_commands(app):
    """Register CLI commands for the application"""
    
    @app.cli.command()
    def init_db():
        """Initialize the database"""
        db.create_all()
        print("Database initialized!")
    
    @app.cli.command()
    def drop_db():
        """Drop all database tables"""
        if input("Are you sure you want to drop all tables? (y/N): ").lower() == 'y':
            db.drop_all()
            print("Database tables dropped!")
        else:
            print("Cancelled.")
    
    @app.cli.command()
    def reset_db():
        """Reset the database (drop and recreate)"""
        if input("Are you sure you want to reset the database? (y/N): ").lower() == 'y':
            db.drop_all()
            db.create_all()
            print("Database reset!")
        else:
            print("Cancelled.")
    
    @app.cli.command()
    def clear_cache():
        """Clear all cached data"""
        if cache_service.flush_all():
            print("Cache cleared!")
        else:
            print("No cache available or error clearing cache.")
    
    @app.cli.command()
    def fix_friendships():
        """Fix existing friendships to be bidirectional"""
        from models import Friend, User
        
        print("🔧 Fixing friendships to be bidirectional...")
        
        # Get all existing friendships
        friendships = Friend.query.all()
        fixed_count = 0
        
        for friendship in friendships:
            # Check if the reverse friendship exists
            reverse_friendship = Friend.query.filter_by(
                user_id=friendship.friend_user_id,
                friend_user_id=friendship.user_id
            ).first()
            
            if not reverse_friendship:
                # Create the reverse friendship
                reverse_friend = Friend(
                    user_id=friendship.friend_user_id,
                    friend_user_id=friendship.user_id
                )
                db.session.add(reverse_friend)
                fixed_count += 1
                print(f"✅ Added reverse friendship: {friendship.user_id} <-> {friendship.friend_user_id}")
        
        if fixed_count > 0:
            db.session.commit()
            print(f"🎉 Fixed {fixed_count} friendships!")
        else:
            print("✅ All friendships are already bidirectional!")
    
    @app.cli.command()
    def debug_friendships():
        """Debug friendship data for specific users"""
        from models import Friend, FriendRequest, User
        
        username1 = input("Enter first username: ").strip()
        username2 = input("Enter second username: ").strip()
        
        # Find users
        user1 = User.query.filter_by(mutual_order_username=username1).first()
        if not user1:
            user1 = User.query.filter_by(discogs_username=username1).first()
        
        user2 = User.query.filter_by(mutual_order_username=username2).first()
        if not user2:
            user2 = User.query.filter_by(discogs_username=username2).first()
        
        if not user1 or not user2:
            print("❌ One or both users not found")
            return
        
        print(f"🔍 User 1: {user1.username} (ID: {user1.id})")
        print(f"🔍 User 2: {user2.username} (ID: {user2.id})")
        
        # Check friendships
        friendship_1_to_2 = Friend.query.filter_by(user_id=user1.id, friend_user_id=user2.id).first()
        friendship_2_to_1 = Friend.query.filter_by(user_id=user2.id, friend_user_id=user1.id).first()
        
        print(f"\n📊 Friendships:")
        print(f"  {user1.username} → {user2.username}: {'✅' if friendship_1_to_2 else '❌'}")
        print(f"  {user2.username} → {user1.username}: {'✅' if friendship_2_to_1 else '❌'}")
        
        # Check friend requests
        requests_1_to_2 = FriendRequest.query.filter_by(requester_id=user1.id, requested_id=user2.id).all()
        requests_2_to_1 = FriendRequest.query.filter_by(requester_id=user2.id, requested_id=user1.id).all()
        
        print(f"\n📨 Friend Requests:")
        print(f"  {user1.username} → {user2.username}: {len(requests_1_to_2)} requests")
        for req in requests_1_to_2:
            print(f"    - Status: {req.status}, Created: {req.created_at}")
        
        print(f"  {user2.username} → {user1.username}: {len(requests_2_to_1)} requests")
        for req in requests_2_to_1:
            print(f"    - Status: {req.status}, Created: {req.created_at}")
    
    @app.cli.command()
    def clean_friendships():
        """Clean all friendship data for specific users"""
        from models import Friend, FriendRequest, User
        
        username1 = input("Enter first username: ").strip()
        username2 = input("Enter second username: ").strip()
        
        # Find users
        user1 = User.query.filter_by(mutual_order_username=username1).first()
        if not user1:
            user1 = User.query.filter_by(discogs_username=username1).first()
        
        user2 = User.query.filter_by(mutual_order_username=username2).first()
        if not user2:
            user2 = User.query.filter_by(discogs_username=username2).first()
        
        if not user1 or not user2:
            print("❌ One or both users not found")
            return
        
        confirm = input(f"⚠️  This will delete ALL friendship data between {user1.username} and {user2.username}. Continue? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Cancelled")
            return
        
        # Delete friendships
        friendships_deleted = 0
        for friendship in Friend.query.filter(
            ((Friend.user_id == user1.id) & (Friend.friend_user_id == user2.id)) |
            ((Friend.user_id == user2.id) & (Friend.friend_user_id == user1.id))
        ).all():
            db.session.delete(friendship)
            friendships_deleted += 1
        
        # Delete friend requests
        requests_deleted = 0
        for request in FriendRequest.query.filter(
            ((FriendRequest.requester_id == user1.id) & (FriendRequest.requested_id == user2.id)) |
            ((FriendRequest.requester_id == user2.id) & (FriendRequest.requested_id == user1.id))
        ).all():
            db.session.delete(request)
            requests_deleted += 1
        
        db.session.commit()
        print(f"✅ Deleted {friendships_deleted} friendships and {requests_deleted} friend requests")
    
    @app.cli.command()
    def nuke_friendships():
        """⚠️  NUCLEAR OPTION: Delete ALL friendship and friend request data"""
        from models import Friend, FriendRequest
        
        confirm = input("⚠️  This will delete ALL friendships and friend requests. Type 'DELETE ALL' to confirm: ")
        if confirm != "DELETE ALL":
            print("❌ Operation cancelled")
            return
        
        # Count before deletion
        friendship_count = Friend.query.count()
        request_count = FriendRequest.query.count()
        
        print(f"🗑️  Deleting {friendship_count} friendships and {request_count} friend requests...")
        
        # Delete all friendships
        Friend.query.delete()
        
        # Delete all friend requests
        FriendRequest.query.delete()
        
        db.session.commit()
        
        print("💥 NUCLEAR CLEANUP COMPLETE! All friendship data has been deleted.")
        print("✅ You can now add friends fresh from the start.")

    @app.cli.command()
    def debug_user_friendships():
        """Debug all friendship data for a specific user"""
        from models import Friend, FriendRequest, User
        
        username = input("Enter username to debug: ").strip()
        if not username:
            print("❌ Username is required")
            return
        
        # Find user
        user = User.query.filter_by(mutual_order_username=username).first()
        if not user:
            user = User.query.filter_by(discogs_username=username).first()
        
        if not user:
            print("❌ User not found")
            return
        
        print(f"🔍 Debugging friendships for: {user.username} (ID: {user.id})")
        print(f"   Mutual Order Username: {user.mutual_order_username}")
        print(f"   Discogs Username: {user.discogs_username}")
        print()
        
        # Check friendships where this user is the main user
        friendships_as_user = Friend.query.filter_by(user_id=user.id).all()
        print(f"👥 Friendships where {user.username} is the main user:")
        for friendship in friendships_as_user:
            friend_user = User.query.get(friendship.friend_user_id)
            print(f"   - {friend_user.username} (ID: {friendship.friend_user_id})")
        
        # Check friendships where this user is the friend
        friendships_as_friend = Friend.query.filter_by(friend_user_id=user.id).all()
        print(f"👥 Friendships where {user.username} is the friend:")
        for friendship in friendships_as_friend:
            main_user = User.query.get(friendship.user_id)
            print(f"   - {main_user.username} (ID: {friendship.user_id})")
        
        # Check outgoing friend requests
        outgoing_requests = FriendRequest.query.filter_by(requester_id=user.id).all()
        print(f"📤 Outgoing friend requests from {user.username}:")
        for request in outgoing_requests:
            requested_user = User.query.get(request.requested_id)
            print(f"   - To: {requested_user.username} (Status: {request.status})")
        
        # Check incoming friend requests
        incoming_requests = FriendRequest.query.filter_by(requested_id=user.id).all()
        print(f"📥 Incoming friend requests to {user.username}:")
        for request in incoming_requests:
            requester_user = User.query.get(request.requester_id)
            print(f"   - From: {requester_user.username} (Status: {request.status})")
        
        print(f"\n📊 Summary:")
        print(f"   - Total friendships as main user: {len(friendships_as_user)}")
        print(f"   - Total friendships as friend: {len(friendships_as_friend)}")
        print(f"   - Outgoing requests: {len(outgoing_requests)}")
        print(f"   - Incoming requests: {len(incoming_requests)}")
    
    @app.cli.command()
    def create_admin():
        """Create an admin user"""
        from models import User
        
        discogs_username = input("Enter Discogs username: ")
        mutual_order_username = input("Enter Mutual Order username: ")
        
        if not discogs_username or not mutual_order_username:
            print("Both usernames are required!")
            return
        
        # Check if user already exists
        existing_user = User.query.filter_by(discogs_username=discogs_username).first()
        if existing_user:
            existing_user.is_admin = True
            existing_user.mutual_order_username = mutual_order_username
            existing_user.profile_completed = True
        else:
            user = User(
                discogs_username=discogs_username,
                mutual_order_username=mutual_order_username,
                discogs_access_token='dummy_token',  # Will be replaced on first login
                discogs_access_secret='dummy_secret',
                is_admin=True,
                profile_completed=True
            )
            db.session.add(user)
        
        try:
            db.session.commit()
            print(f"Admin user '{mutual_order_username}' created/updated!")
        except Exception as e:
            db.session.rollback()
            print(f"Error creating admin user: {e}")


    @app.context_processor
    def inject_user():
        from services import auth_service
        if auth_service.is_authenticated():
            return dict(current_user=auth_service.get_current_user())
        return dict(current_user=None)
    
# Application factory setup
app = None

def get_app():
    """Get or create the Flask application instance"""
    global app
    if app is None:
        app = create_app()
        register_cli_commands(app)
    return app

# For direct execution or WSGI
if __name__ == "__main__":
    app = get_app()
    
    # Development server configuration
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    port = int(os.environ.get('PORT', 5001))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"🚀 Starting Mutual Order application...")
    print(f"📍 Server: http://{host}:{port}")
    print(f"🔧 Debug mode: {debug_mode}")
    print(f"⚙️  Environment: {os.environ.get('FLASK_CONFIG', 'development')}")
    
    app.run(
        host=host,
        port=port,
        debug=debug_mode,
        threaded=True
    )
else:
    # For WSGI servers (Gunicorn, uWSGI, etc.)
    app = get_app()