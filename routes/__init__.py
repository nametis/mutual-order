from flask import Blueprint
from .auth import auth_bp
from .views import views_bp
from .api import api_bp

def register_blueprints(app):
    """Register all blueprints with the Flask application"""
    
    # Register authentication routes
    app.register_blueprint(auth_bp)
    
    # Register main view routes (no prefix, these are the main pages)
    app.register_blueprint(views_bp)
    
    # Register API routes
    app.register_blueprint(api_bp)

__all__ = ['register_blueprints', 'auth_bp', 'views_bp', 'api_bp']