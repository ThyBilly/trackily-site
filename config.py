"""
Configuration settings for StockWatch Flask application
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    
    # Flask Settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    


    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '3306')
    DB_NAME = os.environ.get('DB_NAME', 'stockwatch')



    # Database connection parameters with local development fallbacks
    DB_HOST = os.environ.get('DB_HOST') or 'localhost'
    DB_PORT = int(os.environ.get('DB_PORT') or 3306)
    DB_NAME = os.environ.get('DB_NAME') or 'stockwatch'
    DB_USER = os.environ.get('DB_USERNAME') or 'billy'
    DB_PASSWORD = os.environ.get('DB_PASSWORD') or '1234'  # Local development password
    
    # SQLAlchemy Database Settings
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'max_overflow': 0
    }
    
    # JWT Settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=90)
    JWT_ALGORITHM = 'HS256'
    
    # CORS Settings
    CORS_ORIGINS = [
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:3000",  # Add other ports if needed
        "http://127.0.0.1:3000"
    ]
    
    # Stripe Settings (from your existing setup)
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_MONTHLY_PRICE = os.environ.get('STRIPE_MONTHLY')
    STRIPE_YEARLY_PRICE = os.environ.get('STRIPE_YEARLY')
    
    # Email Settings (for future email verification)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@stockwatch.com'
    
    # Security Settings
    WTF_CSRF_ENABLED = False  # Disabled for API endpoints
    
    # Application Settings
    APP_NAME = 'StockWatch'
    APP_VERSION = '1.0.0'
    
    # Pagination
    POSTS_PER_PAGE = 25
    
    # Rate Limiting (requests per minute)
    RATELIMIT_DEFAULT = "100 per minute"
    RATELIMIT_STORAGE_URL = "memory://"
    
    @staticmethod
    def is_local_development():
        """Check if running in local development environment"""
        return not os.environ.get('DB_HOST') or os.environ.get('FLASK_ENV') == 'development'
    
    @classmethod
    def init_app(cls, app):
        """Initialize application with config"""
        # Log the configuration being used
        if cls.is_local_development():
            print(f"🔧 Using LOCAL development database: {cls.DB_USER}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}")
        else:
            print(f"🌐 Using PRODUCTION database: {cls.DB_USER}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}")

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    
    # More verbose logging in development
    LOG_LEVEL = 'DEBUG'
    
    # Shorter token expiry for testing
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # Local development database settings (override if needed)
    DB_HOST = os.environ.get('DB_HOST') or 'localhost'
    DB_PORT = int(os.environ.get('DB_PORT') or 3306)
    DB_NAME = os.environ.get('DB_NAME') or 'stockwatch'
    DB_USER = os.environ.get('DB_USERNAME') or 'billy'
    DB_PASSWORD = os.environ.get('DB_PASSWORD') or '1234'  # Local development password
    
    # Rebuild SQLAlchemy URI with local settings
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        print("🚀 Development mode: Debug enabled, using local database")

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Security headers
    SECURITY_HEADERS = {
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Content-Security-Policy': "default-src 'self'"
    }
    
    # Production logging
    LOG_LEVEL = 'WARNING'
    
    # Longer token expiry in production
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)
    
    # Production CORS (more restrictive)
    CORS_ORIGINS = [
        os.environ.get('FRONTEND_URL', 'https://stockwatch.com')
    ]
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Ensure required environment variables are set in production
        required_vars = ['DB_HOST', 'DB_USERNAME', 'DB_PASSWORD', 'SECRET_KEY', 'JWT_SECRET_KEY']
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        print("🔒 Production mode: Security headers enabled, environment validated")

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    
    # Use test database
    DB_NAME = 'stockwatch_test'
    
    # Override SQLAlchemy URI for testing
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/stockwatch_test"
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Short token expiry for testing
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        print("🧪 Testing mode: Using test database")

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    flask_env = os.environ.get('FLASK_ENV', 'development').lower()
    
    if flask_env == 'production':
        return ProductionConfig
    elif flask_env == 'testing':
        return TestingConfig
    else:
        return DevelopmentConfig