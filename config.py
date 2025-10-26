import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration class"""
    # SECRET_KEY must be set via environment variable in production
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY = os.getenv('SECRET_KEY', "dev_key_change_in_production")
    
    # Verify SECRET_KEY is set properly in production
    if SECRET_KEY == "dev_key_change_in_production" and os.getenv('FLASK_CONFIG') == 'production':
        import warnings
        warnings.warn("⚠️ SECRET_KEY is using default value! Set SECRET_KEY in environment variables.")
    
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///mutual_order.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # CSRF Protection - ENABLED for security
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Discogs API
    DISCOGS_CONSUMER_KEY = os.getenv('DISCOGS_CONSUMER_KEY')
    DISCOGS_CONSUMER_SECRET = os.getenv('DISCOGS_CONSUMER_SECRET')
    DISCOGS_ACCESS_TOKEN = os.getenv('DISCOGS_ACCESS_TOKEN')
    DISCOGS_ACCESS_SECRET = os.getenv('DISCOGS_ACCESS_SECRET')
    
    # Rate limiting
    DISCOGS_RATE_LIMIT_PER_MINUTE = 60
    
    # Background jobs
    ENABLE_BACKGROUND_JOBS = False  # Disabled - incremental updates handle this more efficiently
    
    # OAuth URLs
    DISCOGS_REQUEST_TOKEN_URL = 'https://api.discogs.com/oauth/request_token'
    DISCOGS_AUTHORIZE_URL = 'https://www.discogs.com/oauth/authorize'
    DISCOGS_ACCESS_TOKEN_URL = 'https://api.discogs.com/oauth/access_token'
    DISCOGS_CALLBACK_URL = 'https://mutual-order.ddns.net/auth/discogs/callback'
    
    # User agent
    USER_AGENT = "MutualOrder/1.0"

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///mutual_order_dev.db')
    # CSRF can be disabled in development for easier testing
    WTF_CSRF_ENABLED = os.getenv('CSRF_ENABLED', 'True').lower() == 'true'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}