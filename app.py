from datetime import timedelta
from flask import Flask, render_template, Blueprint, request, g
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import get_config
import os
import logging
import logging.handlers
from datetime import datetime
import time

db = SQLAlchemy()
jwt = JWTManager()

def setup_logging(app):
    """Configure logging for the application"""
    
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup main application logger
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.INFO)
    
    # Setup file handler for general application logs
    app_file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    app_file_handler.setFormatter(formatter)
    app_logger.addHandler(app_file_handler)
    
    # Setup file handler for route activity
    route_logger = logging.getLogger('routes')
    route_logger.setLevel(logging.INFO)
    
    route_file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'routes.log'),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    route_file_handler.setFormatter(formatter)
    route_logger.addHandler(route_file_handler)
    
    # Setup error logger
    error_logger = logging.getLogger('errors')
    error_logger.setLevel(logging.ERROR)
    
    error_file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'errors.log'),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    error_file_handler.setFormatter(formatter)
    error_logger.addHandler(error_file_handler)
    
    # Also add console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    app_logger.addHandler(console_handler)
    
    # Set Flask's logger to use our configuration
    app.logger.handlers.clear()
    app.logger.addHandler(app_file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)
    
    return app_logger, route_logger, error_logger

def log_request_info():
    """Log information about incoming requests"""
    g.start_time = time.time()
    route_logger = logging.getLogger('routes')
    
    # Log request details
    route_logger.info(f"Request: {request.method} {request.path} | "
                     f"IP: {request.remote_addr} | "
                     f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}")

def log_response_info(response):
    """Log information about outgoing responses"""
    route_logger = logging.getLogger('routes')
    
    # Calculate request duration
    duration = time.time() - g.get('start_time', time.time())
    
    # Log response details
    route_logger.info(f"Response: {response.status_code} | "
                     f"Duration: {duration:.3f}s | "
                     f"Size: {response.content_length or 0} bytes")
    
    return response

def create_app(config_class=None):
    app = Flask(__name__, 
                static_folder='static',
                static_url_path='')
    
    # Get configuration based on environment if not provided
    if config_class is None:
        config_class = get_config()
    
    app.config.from_object(config_class)
    
    # Initialize the config with the app
    config_class.init_app(app)
    
    # Setup logging
    app_logger, route_logger, error_logger = setup_logging(app)
    
    # Log startup information
    app_logger.info("="*60)
    app_logger.info("FLASK APPLICATION STARTUP")
    app_logger.info("="*60)
    app_logger.info(f"Application Name: {app.name}")
    app_logger.info(f"Environment: {os.environ.get('FLASK_ENV', 'production')}")
    app_logger.info(f"Debug Mode: {app.debug}")
    app_logger.info(f"Config Class: {config_class.__name__}")
    app_logger.info(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')}")
    app_logger.info(f"Secret Key Set: {'Yes' if app.config.get('SECRET_KEY') else 'No'}")
    app_logger.info(f"CORS Origins: {app.config.get('CORS_ORIGINS', 'Default')}")
    app_logger.info(f"Startup Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    app_logger.info("="*60)

    # CORS Configuration - use config values
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config.get('CORS_ORIGINS', ["http://localhost:4200", "http://localhost:5000", "http://127.0.0.1:5000"]),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    
    # Setup request/response logging middleware
    app.before_request(log_request_info)
    app.after_request(log_response_info)

    # JWT Error Handlers with logging
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        error_logger.warning(f"Expired token access attempt from {request.remote_addr}")
        return {'error': 'Token has expired'}, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        error_logger.warning(f"Invalid token access attempt from {request.remote_addr}: {error}")
        return {'error': 'Invalid token'}, 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        error_logger.warning(f"Unauthorized access attempt from {request.remote_addr}: {error}")
        return {'error': 'Authorization token is required'}, 401

    # Global error handler
    @app.errorhandler(Exception)
    def handle_exception(e):
        error_logger.error(f"Unhandled exception: {str(e)} | "
                          f"Route: {request.method} {request.path} | "
                          f"IP: {request.remote_addr}", exc_info=True)
        
        # Return a generic error message for production
        if app.debug:
            raise e
        else:
            return {'error': 'Internal server error'}, 500

    # Create main blueprint for static pages
    main_bp = Blueprint('main', __name__)
    
    @main_bp.route('/')
    def home():
        """Route to display the home page"""
        app_logger.info("Home page accessed")
        return render_template('index.html')

    @main_bp.route('/register')
    def register_page():
        """Route to display the registration page"""
        app_logger.info("Register page accessed")
        return render_template('register.html')

    @main_bp.route('/login')
    def login_page():
        """Route to display the login page"""
        app_logger.info("Login page accessed")
        return render_template('login.html')

    @main_bp.route('/about')
    def about():
        """Route to display the About page"""
        return render_template('about.html')

    @main_bp.route('/pricing')
    def pricing():
        """Route to display the pricing page"""
        return render_template('pricing.html')

    @main_bp.route('/contact')
    def contact():
        """Route to display the contact page"""
        return render_template('contact.html')

    @main_bp.route('/terms')
    def terms():
        """Route to display the terms of service"""
        return render_template('terms.html')

    @main_bp.route('/privacy')
    def privacy():
        """Route to display the privacy policy"""
        return render_template('privacy.html')
    
    @main_bp.route('/forgot-password')
    def forgot_password_page():
        """Route to display the forgot password page"""
        return render_template('forgot-password.html')

    @main_bp.route('/reset-password')
    def reset_password_page():
        """Route to display the reset password page"""
        return render_template('reset-password.html')

    # Dashboard page routes
    @main_bp.route('/dashboard')
    def dashboard_page():
        """Main dashboard page"""
        app_logger.info("Dashboard page accessed")
        return render_template('dashboard/dashboard.html')

    @main_bp.route('/dashboard/tracking')
    def tracking_page():
        """Price tracking page"""
        return render_template('dashboard/tracking.html')

    @main_bp.route('/dashboard/settings')
    def settings_page():
        """Settings page"""
        return render_template('dashboard/settings.html')

    @main_bp.route('/dashboard/premium')
    def premium_page():
        """Premium subscription management page"""
        return render_template('dashboard/premium.html')

    # Register the main blueprint
    app.register_blueprint(main_bp)
    
    # Import and register the dashboard API blueprint
    try:
        from app.routes.dashboard.route import dashboard_bp
        app.register_blueprint(dashboard_bp)
        app_logger.info("Dashboard blueprint registered successfully")
    except ImportError as e:
        app_logger.warning(f"Failed to import dashboard blueprint: {e}")
    
    # Import and register the premium API blueprint
    try:
        from app.routes.premium.route import premium_bp
        app.register_blueprint(premium_bp)
        app_logger.info("Premium blueprint registered successfully")
    except ImportError as e:
        app_logger.warning(f"Failed to import premium blueprint: {e}")
    
    # Import and register the auth blueprint (fixed import path)
    try:
        from app.routes.auth.route import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        app_logger.info("Auth blueprint registered successfully")
    except ImportError as e:
        app_logger.warning(f"Failed to import auth blueprint: {e}")
    
    # Import and register the password reset blueprint
    try:
        from app.routes.password.route import password_bp
        app.register_blueprint(password_bp, url_prefix='/api/password')
        app_logger.info("Password blueprint registered successfully")
    except ImportError as e:
        app_logger.warning(f"Failed to import password blueprint: {e}")
    
    # Import and register the stripe blueprint (existing)
    try:
        from app.routes.stripe.route import stripe_bp
        app.register_blueprint(stripe_bp, url_prefix='/api/stripe')
        app_logger.info("Stripe blueprint registered successfully")
    except ImportError as e:
        app_logger.warning(f"Failed to import stripe blueprint: {e}")
    
    # Log final startup message
    app_logger.info("Flask application startup completed successfully")
    app_logger.info(f"Server ready to accept connections")

    return app

if __name__ == '__main__':
    app = create_app()
    
    # Log the server start
    app_logger = logging.getLogger('app')
    app_logger.info("Starting Flask development server...")
    
    try:
        app.run(debug=True)
    except KeyboardInterrupt:
        app_logger.info("Flask server shutdown initiated by user")
    except Exception as e:
        error_logger = logging.getLogger('errors')
        error_logger.error(f"Flask server crashed: {str(e)}", exc_info=True)
        raise