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