from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.db import Database
import re
import os
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

def log_auth_event(event_type, details):
    """Helper function to log authentication events with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[AUTH {timestamp}] {event_type}: {details}")

def handle_preflight():
    """Handle CORS preflight requests"""
    response = jsonify({'message': 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response, 200

def add_cors_headers(response):
    """Add CORS headers to response"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

def validate_email(email):
    """Validate email format"""
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"

@auth_bp.route('/register', methods=['POST', 'OPTIONS'])
def register():
    """Register a new user"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        data = request.get_json()
        
        if not data:
            log_auth_event("REGISTRATION_FAILED", "No data provided in request")
            response = jsonify({'error': 'No data provided'})
            return add_cors_headers(response), 400
        
        # Extract and validate required fields
        full_name = data.get('fullName', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        newsletter = data.get('newsletter', False)
        
        log_auth_event("REGISTRATION_ATTEMPT", f"Email: {email}, Name: {full_name}")
        
        # Validation
        if not full_name or len(full_name) < 2:
            log_auth_event("REGISTRATION_FAILED", f"Invalid full name for {email}: '{full_name}'")
            response = jsonify({'error': 'Full name is required and must be at least 2 characters'})
            return add_cors_headers(response), 400
        
        if not email or not validate_email(email):
            log_auth_event("REGISTRATION_FAILED", f"Invalid email format: {email}")
            response = jsonify({'error': 'Valid email address is required'})
            return add_cors_headers(response), 400
        
        password_valid, password_message = validate_password(password)
        if not password_valid:
            log_auth_event("REGISTRATION_FAILED", f"Weak password for {email}: {password_message}")
            response = jsonify({'error': password_message})
            return add_cors_headers(response), 400
        
        # Hash password
        password_hash = generate_password_hash(password)
        
        # Call database procedure to create user
        result = Database.call_procedure('create_user_account', {
            'p_full_name': full_name,
            'p_email': email,
            'p_password_hash': password_hash,
            'p_newsletter_opt_in': newsletter
        })
        
        if not result or len(result) == 0:
            log_auth_event("REGISTRATION_FAILED", f"Database error for {email}: No response from database")
            response = jsonify({'error': 'Registration failed - no response from database'})
            return add_cors_headers(response), 500
        
        row = result[0]
        status = row[0]
        message = row[1]
        
        if status != 'success':
            log_auth_event("REGISTRATION_FAILED", f"Database error for {email}: {message}")
            response = jsonify({'error': message})
            return add_cors_headers(response), 400
        
        # Registration successful
        log_auth_event("REGISTRATION_SUCCESS", f"New user registered - Email: {email}, Name: {full_name}, Newsletter: {newsletter}")
        
        response = jsonify({
            'message': 'Account created successfully',
            'user': {
                'email': email,
                'full_name': full_name
            }
        })
        return add_cors_headers(response), 201
        
    except Exception as e:
        log_auth_event("REGISTRATION_ERROR", f"Exception during registration: {str(e)}")
        print(f"Registration error: {str(e)}")
        response = jsonify({'error': 'Internal server error during registration'})
        return add_cors_headers(response), 500

@auth_bp.route('/login', methods=['POST', 'OPTIONS'])
def login():
    """Authenticate user and return JWT tokens"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        data = request.get_json()
        
        if not data:
            log_auth_event("LOGIN_FAILED", "No data provided in request")
            response = jsonify({'error': 'No data provided'})
            return add_cors_headers(response), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        remember = data.get('remember', False)
        
        log_auth_event("LOGIN_ATTEMPT", f"Email: {email}, Remember: {remember}")
        
        # Validation
        if not email or not password:
            log_auth_event("LOGIN_FAILED", f"Missing credentials for {email}")
            response = jsonify({'error': 'Email and password are required'})
            return add_cors_headers(response), 400
        
        # Call database procedure to verify user credentials
        result = Database.call_procedure('verify_user_login', {
            'p_email': email
        })
        
        print(f"DEBUG: verify_user_login result = {result}")
        
        if not result or len(result) == 0:
            log_auth_event("LOGIN_FAILED", f"User not found: {email}")
            response = jsonify({'error': 'Invalid email or password'})
            return add_cors_headers(response), 401
        
        row = result[0]
        status = row[0]
        message = row[1]
        
        if status != 'success':
            log_auth_event("LOGIN_FAILED", f"Database error for {email}: {message}")
            response = jsonify({'error': 'Invalid email or password'})
            return add_cors_headers(response), 401
        
        # Extract user data from procedure result
        # verify_user_login returns: [('success', 'User found', user_id, password_hash, full_name, email_verified, is_active)]
        user_id = row[2]              # Index 2: user_id
        stored_password_hash = row[3] # Index 3: password_hash
        full_name = row[4]            # Index 4: full_name
        email_verified = row[5]       # Index 5: email_verified
        is_active = row[6]            # Index 6: is_active
        
        print(f"DEBUG: Extracted data - user_id={user_id}, full_name={full_name}, email_verified={email_verified}, is_active={is_active}")
        
        # Verify password
        if not check_password_hash(stored_password_hash, password):
            log_auth_event("LOGIN_FAILED", f"Invalid password for {email}")
            response = jsonify({'error': 'Invalid email or password'})
            return add_cors_headers(response), 401
        
        # Check if account is active
        if not is_active:
            log_auth_event("LOGIN_FAILED", f"Inactive account: {email}")
            response = jsonify({'error': 'Account is deactivated. Please contact support.'})
            return add_cors_headers(response), 401
        
        # CRITICAL FIX: Convert user_id to string for JWT
        user_id_str = str(user_id)
        print(f"DEBUG: Converting user_id {user_id} to string '{user_id_str}' for JWT")
        
        # Create JWT tokens
        additional_claims = {
            'email': email,
            'full_name': full_name,
            'email_verified': bool(email_verified)
        }
        
        print(f"DEBUG: Creating JWT token with user_id='{user_id_str}' and claims={additional_claims}")
        
        access_token = create_access_token(
            identity=user_id_str,  # FIXED: Use string instead of int
            additional_claims=additional_claims
        )
        
        refresh_token = create_refresh_token(identity=user_id_str)  # FIXED: Use string
        
        print(f"DEBUG: JWT tokens created successfully")
        
        # Update last login timestamp
        Database.call_procedure('update_user_last_login', {
            'p_user_id': user_id
        })
        
        # Log successful login
        log_auth_event("LOGIN_SUCCESS", f"User logged in - Email: {email}, Name: {full_name}, ID: {user_id}, Email Verified: {email_verified}")
        
        # Prepare response
        response_data = {
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'id': user_id,
                'email': email,
                'full_name': full_name,
                'email_verified': bool(email_verified)
            }
        }
        
        response = jsonify(response_data)
        return add_cors_headers(response), 200
        
    except Exception as e:
        log_auth_event("LOGIN_ERROR", f"Exception during login: {str(e)}")
        print(f"Login error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        response = jsonify({'error': 'Internal server error during login'})
        return add_cors_headers(response), 500

@auth_bp.route('/refresh', methods=['POST', 'OPTIONS'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token using refresh token"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        current_user_id_str = get_jwt_identity()
        print(f"DEBUG: Refresh token - current_user_id_str = '{current_user_id_str}' (type: {type(current_user_id_str)})")
        
        log_auth_event("TOKEN_REFRESH_ATTEMPT", f"User ID: {current_user_id_str}")
        
        # Convert back to int for database query
        try:
            current_user_id = int(current_user_id_str)
        except (ValueError, TypeError):
            print(f"DEBUG: Failed to convert user_id '{current_user_id_str}' to int")
            log_auth_event("TOKEN_REFRESH_FAILED", f"Invalid user ID format: {current_user_id_str}")
            response = jsonify({'error': 'Invalid user ID'})
            return add_cors_headers(response), 401
        
        # Get fresh user data
        result = Database.call_procedure('get_user_by_id', {
            'p_user_id': current_user_id
        })
        
        print(f"DEBUG: get_user_by_id result = {result}")
        
        if not result or len(result) == 0:
            print("DEBUG: No result from get_user_by_id")
            log_auth_event("TOKEN_REFRESH_FAILED", f"User not found for ID: {current_user_id}")
            response = jsonify({'error': 'User not found'})
            return add_cors_headers(response), 404
        
        row = result[0]
        print(f"DEBUG: get_user_by_id row = {row}")
        
        if row[0] != 'success':
            print(f"DEBUG: get_user_by_id failed with status = {row[0]}")
            log_auth_event("TOKEN_REFRESH_FAILED", f"Database error for user ID {current_user_id}: {row[1] if len(row) > 1 else 'Unknown error'}")
            response = jsonify({'error': 'User not found'})
            return add_cors_headers(response), 404
        
        # FIXED: get_user_by_id returns: [('success', 'User found', email, full_name, email_verified)]
        email = row[2]            # Index 2: email
        full_name = row[3]        # Index 3: full_name
        email_verified = row[4]   # Index 4: email_verified
        
        additional_claims = {
            'email': email,
            'full_name': full_name,
            'email_verified': bool(email_verified)
        }
        
        new_access_token = create_access_token(
            identity=current_user_id_str,  # Keep as string
            additional_claims=additional_claims
        )
        
        log_auth_event("TOKEN_REFRESH_SUCCESS", f"Token refreshed for user - Email: {email}, Name: {full_name}, ID: {current_user_id}")
        
        response = jsonify({
            'access_token': new_access_token
        })
        return add_cors_headers(response), 200
        
    except Exception as e:
        log_auth_event("TOKEN_REFRESH_ERROR", f"Exception during token refresh: {str(e)}")
        print(f"Token refresh error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        response = jsonify({'error': 'Token refresh failed'})
        return add_cors_headers(response), 500

@auth_bp.route('/verify-token', methods=['GET', 'OPTIONS'])
@jwt_required()
def verify_token():
    """Verify if current token is valid and return user info"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        # Debug JWT information
        jwt_data = get_jwt()
        current_user_id_str = get_jwt_identity()
        
        print(f"DEBUG: Verify token - JWT data = {jwt_data}")
        print(f"DEBUG: Verify token - current_user_id_str = '{current_user_id_str}' (type: {type(current_user_id_str)})")
        
        log_auth_event("TOKEN_VERIFY_ATTEMPT", f"User ID: {current_user_id_str}")
        
        if current_user_id_str is None:
            print("DEBUG: JWT identity is None!")
            log_auth_event("TOKEN_VERIFY_FAILED", "JWT identity is None")
            response = jsonify({'error': 'Invalid token identity'})
            return add_cors_headers(response), 401
        
        # Convert back to int for database query
        try:
            current_user_id = int(current_user_id_str)
        except (ValueError, TypeError):
            print(f"DEBUG: Failed to convert user_id '{current_user_id_str}' to int")
            log_auth_event("TOKEN_VERIFY_FAILED", f"Invalid user ID format: {current_user_id_str}")
            response = jsonify({'error': 'Invalid user ID format'})
            return add_cors_headers(response), 401
        
        # Get user data
        result = Database.call_procedure('get_user_by_id', {
            'p_user_id': current_user_id
        })
        
        print(f"DEBUG: get_user_by_id result = {result}")
        
        if not result or len(result) == 0:
            print("DEBUG: No result from get_user_by_id")
            log_auth_event("TOKEN_VERIFY_FAILED", f"User not found for ID: {current_user_id}")
            response = jsonify({'error': 'User not found'})
            return add_cors_headers(response), 404
        
        row = result[0]
        print(f"DEBUG: get_user_by_id row = {row}")
        
        if row[0] != 'success':
            print(f"DEBUG: get_user_by_id failed with status = {row[0]}")
            log_auth_event("TOKEN_VERIFY_FAILED", f"Database error for user ID {current_user_id}: {row[1] if len(row) > 1 else 'Unknown error'}")
            response = jsonify({'error': 'User not found'})
            return add_cors_headers(response), 404
        
        # FIXED: get_user_by_id returns: [('success', 'User found', email, full_name, email_verified)]
        email = row[2]            # Index 2: email  
        full_name = row[3]        # Index 3: full_name
        email_verified = row[4]   # Index 4: email_verified
        
        user_data = {
            'id': current_user_id,
            'email': email,
            'full_name': full_name,
            'email_verified': bool(email_verified),
            'name': full_name  # Add 'name' alias for compatibility
        }
        
        print(f"DEBUG: Constructed user_data = {user_data}")
        
        log_auth_event("TOKEN_VERIFY_SUCCESS", f"Token verified for user - Email: {email}, Name: {full_name}, ID: {current_user_id}")
        
        response = jsonify({
            'valid': True,
            'user': user_data
        })
        return add_cors_headers(response), 200
        
    except Exception as e:
        log_auth_event("TOKEN_VERIFY_ERROR", f"Exception during token verification: {str(e)}")
        print(f"Token verification error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        response = jsonify({'error': 'Token verification failed'})
        return add_cors_headers(response), 500

@auth_bp.route('/logout', methods=['POST', 'OPTIONS'])
@jwt_required()
def logout():
    """Logout user (client-side token removal)"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        current_user_id_str = get_jwt_identity()
        current_user_id = int(current_user_id_str)
        
        # Get user info for logging
        result = Database.call_procedure('get_user_by_id', {
            'p_user_id': current_user_id
        })
        
        user_email = "Unknown"
        user_name = "Unknown"
        if result and len(result) > 0 and result[0][0] == 'success':
            user_email = result[0][2]
            user_name = result[0][3]
        
        # Log the logout activity
        Database.call_procedure('update_user_activity', {
            'p_user_id': current_user_id,
            'p_activity_type': 'logout'
        })
        
        log_auth_event("LOGOUT_SUCCESS", f"User logged out - Email: {user_email}, Name: {user_name}, ID: {current_user_id}")
        
        response = jsonify({
            'message': 'Logout successful'
        })
        return add_cors_headers(response), 200
        
    except Exception as e:
        log_auth_event("LOGOUT_ERROR", f"Exception during logout: {str(e)}")
        print(f"Logout error: {str(e)}")
        response = jsonify({'error': 'Logout failed'})
        return add_cors_headers(response), 500

# DEBUG ENDPOINT - Fixed to handle Row objects
@auth_bp.route('/debug-procedures', methods=['GET'])
def debug_procedures():
    """Debug endpoint to check procedure structures"""
    try:
        log_auth_event("DEBUG_ACCESS", "Debug procedures endpoint accessed")
        
        # Test get_user_by_id with known user
        result = Database.call_procedure('get_user_by_id', {'p_user_id': 4})
        
        # Convert Row objects to tuples for JSON serialization
        serializable_result = []
        if result:
            for row in result:
                if hasattr(row, '_asdict'):  # Row object
                    serializable_result.append(tuple(row))
                else:
                    serializable_result.append(row)
        
        log_auth_event("DEBUG_RESULT", f"Debug procedures result: {serializable_result}")
        
        return jsonify({
            'get_user_by_id_result': serializable_result,
            'structure': [f'Index {i}: {serializable_result[0][i]}' for i in range(len(serializable_result[0]))] if serializable_result else []
        })
    except Exception as e:
        log_auth_event("DEBUG_ERROR", f"Exception in debug endpoint: {str(e)}")
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        })