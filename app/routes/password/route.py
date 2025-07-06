from flask import Blueprint, jsonify, request, current_app
from werkzeug.security import generate_password_hash
from app.utils.db import Database
import secrets
import string
from datetime import datetime, timedelta
import os
import re

password_bp = Blueprint('password', __name__)

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

def generate_secure_token(length=32):
    """Generate a cryptographically secure random token"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def send_password_reset_email(email, reset_token, user_name):
    """
    Send password reset email to user
    For now, this will just log the email details to console
    You can implement actual email sending later
    """
    try:
        # Create reset URL
        base_url = os.getenv('BASE_URL', 'http://localhost:5000')
        reset_url = f"{base_url}/reset-password?token={reset_token}"
        
        # For now, just log the email details
        print("=" * 60)
        print("📧 PASSWORD RESET EMAIL")
        print("=" * 60)
        print(f"To: {email}")
        print(f"User: {user_name}")
        print(f"Reset URL: {reset_url}")
        print("=" * 60)
        print("Email Content:")
        print(f"""
Subject: Reset Your StockWatch Password

Hi {user_name},

We received a request to reset your password for your StockWatch account.

Click this link to reset your password:
{reset_url}

This link will expire in 24 hours and can only be used once.

If you didn't request a password reset, you can safely ignore this email.

Thanks,
The StockWatch Team
        """)
        print("=" * 60)
        
        # Return True to simulate successful email sending
        # In a real implementation, you'd actually send the email here
        return True
        
    except Exception as e:
        print(f"Error preparing password reset email: {str(e)}")
        return False

def send_actual_email(email, reset_token, user_name):
    """
    Alternative email implementation using requests to external service
    Uncomment and configure this if you want to use a service like SendGrid
    """
    # Example using requests to send via SendGrid API
    # import requests
    # 
    # api_key = os.getenv('SENDGRID_API_KEY')
    # if not api_key:
    #     return False
    #     
    # base_url = os.getenv('BASE_URL', 'http://localhost:5000')
    # reset_url = f"{base_url}/reset-password?token={reset_token}"
    # 
    # data = {
    #     "personalizations": [{
    #         "to": [{"email": email}],
    #         "subject": "Reset Your StockWatch Password"
    #     }],
    #     "from": {"email": "noreply@stockwatch.com", "name": "StockWatch"},
    #     "content": [{
    #         "type": "text/html",
    #         "value": f"""
    #         <h2>Password Reset Request</h2>
    #         <p>Hi {user_name},</p>
    #         <p>Click <a href="{reset_url}">here</a> to reset your password.</p>
    #         <p>This link expires in 24 hours.</p>
    #         """
    #     }]
    # }
    # 
    # headers = {
    #     'Authorization': f'Bearer {api_key}',
    #     'Content-Type': 'application/json'
    # }
    # 
    # response = requests.post(
    #     'https://api.sendgrid.com/v3/mail/send',
    #     json=data,
    #     headers=headers
    # )
    # 
    # return response.status_code == 202
    
    return False

@password_bp.route('/forgot-password', methods=['POST', 'OPTIONS'])
def forgot_password():
    """Send password reset email"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        data = request.get_json()
        
        if not data:
            response = jsonify({'error': 'No data provided'})
            return add_cors_headers(response), 400
        
        email = data.get('email', '').strip().lower()
        
        # Validate email
        if not email or not validate_email(email):
            response = jsonify({'error': 'Valid email address is required'})
            return add_cors_headers(response), 400
        
        # Check if user exists (but don't reveal if they don't for security)
        result = Database.call_procedure('get_user_by_email', {
            'p_email': email
        })
        
        if not result or len(result) == 0 or result[0][0] != 'success':
            # For security, always return success even if user doesn't exist
            response = jsonify({
                'message': 'If an account with that email exists, we have sent a password reset link.',
                'email': email
            })
            return add_cors_headers(response), 200
        
        # User exists, get their information
        user_id = result[0][2]
        full_name = result[0][3]
        is_active = result[0][4]
        
        if not is_active:
            # Don't reveal that account is deactivated
            response = jsonify({
                'message': 'If an account with that email exists, we have sent a password reset link.',
                'email': email
            })
            return add_cors_headers(response), 200
        
        # Generate secure reset token
        reset_token = generate_secure_token(64)
        expires_at = datetime.now() + timedelta(hours=24)
        
        # Store reset token in database
        token_result = Database.call_procedure('create_password_reset_token', {
            'p_user_id': user_id,
            'p_token': reset_token,
            'p_expires_at': expires_at.strftime('%Y-%m-%d %H:%M:%S')
        })
        
        if not token_result or len(token_result) == 0 or token_result[0][0] != 'success':
            response = jsonify({'error': 'Failed to generate reset token'})
            return add_cors_headers(response), 500
        
        # Send password reset email (currently just logs to console)
        email_sent = send_password_reset_email(email, reset_token, full_name)
        
        if not email_sent:
            # Log the error but still return success for security
            print(f"Failed to send password reset email to {email}")
        
        # Always return success for security (don't reveal if email failed)
        response = jsonify({
            'message': 'If an account with that email exists, we have sent a password reset link.',
            'email': email
        })
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Forgot password error: {str(e)}")
        response = jsonify({'error': 'Internal server error'})
        return add_cors_headers(response), 500

@password_bp.route('/verify-token', methods=['POST', 'OPTIONS'])
def verify_reset_token():
    """Verify if password reset token is valid"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        data = request.get_json()
        
        if not data:
            response = jsonify({'error': 'No data provided'})
            return add_cors_headers(response), 400
        
        token = data.get('token', '').strip()
        
        if not token:
            response = jsonify({'error': 'Reset token is required'})
            return add_cors_headers(response), 400
        
        # Verify token in database
        result = Database.call_procedure('verify_password_reset_token', {
            'p_token': token
        })
        
        if not result or len(result) == 0:
            response = jsonify({'error': 'Invalid or expired reset token'})
            return add_cors_headers(response), 400
        
        row = result[0]
        status = row[0]
        message = row[1]
        
        if status != 'success':
            response = jsonify({'error': message})
            return add_cors_headers(response), 400
        
        # Token is valid
        user_id = row[2]
        user_email = row[3]
        user_name = row[4]
        
        response = jsonify({
            'message': 'Token is valid',
            'user': {
                'id': user_id,
                'email': user_email,
                'name': user_name
            }
        })
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Token verification error: {str(e)}")
        response = jsonify({'error': 'Internal server error'})
        return add_cors_headers(response), 500

@password_bp.route('/reset-password', methods=['POST', 'OPTIONS'])
def reset_password():
    """Reset user password with valid token"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        data = request.get_json()
        
        if not data:
            response = jsonify({'error': 'No data provided'})
            return add_cors_headers(response), 400
        
        token = data.get('token', '').strip()
        new_password = data.get('password', '')
        
        # Validate inputs
        if not token:
            response = jsonify({'error': 'Reset token is required'})
            return add_cors_headers(response), 400
        
        password_valid, password_message = validate_password(new_password)
        if not password_valid:
            response = jsonify({'error': password_message})
            return add_cors_headers(response), 400
        
        # Verify token is still valid
        verify_result = Database.call_procedure('verify_password_reset_token', {
            'p_token': token
        })
        
        if not verify_result or len(verify_result) == 0 or verify_result[0][0] != 'success':
            response = jsonify({'error': 'Invalid or expired reset token'})
            return add_cors_headers(response), 400
        
        user_id = verify_result[0][2]
        
        # Hash the new password
        password_hash = generate_password_hash(new_password)
        
        # Reset the password and invalidate the token
        reset_result = Database.call_procedure('reset_user_password', {
            'p_token': token,
            'p_user_id': user_id,
            'p_new_password_hash': password_hash
        })
        
        if not reset_result or len(reset_result) == 0:
            response = jsonify({'error': 'Failed to reset password'})
            return add_cors_headers(response), 500
        
        row = reset_result[0]
        status = row[0]
        message = row[1]
        
        if status != 'success':
            response = jsonify({'error': message})
            return add_cors_headers(response), 400
        
        response = jsonify({
            'message': 'Password reset successfully'
        })
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Password reset error: {str(e)}")
        response = jsonify({'error': 'Internal server error'})
        return add_cors_headers(response), 500

@password_bp.route('/resend-reset', methods=['POST', 'OPTIONS'])
def resend_reset_email():
    """Resend password reset email"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    # This endpoint has the same logic as forgot_password
    # but with a different rate limit (could implement rate limiting here)
    return forgot_password()