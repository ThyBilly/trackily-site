from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.db import Database
import re
from urllib.parse import urlparse

dashboard_bp = Blueprint('dashboard', __name__)

def add_cors_headers(response):
    """Add CORS headers to response"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    return response

def handle_preflight():
    """Handle CORS preflight requests"""
    response = jsonify({'message': 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response, 200

def validate_url(url):
    """Validate if URL is properly formatted"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def extract_product_info(url):
    """Extract product information from URL"""
    parsed_url = urlparse(url.lower())
    domain = parsed_url.netloc.replace('www.', '')
    
    if 'amazon.' in domain:
        return {'store': 'Amazon', 'title': 'Amazon Product'}
    elif 'ebay.' in domain:
        return {'store': 'eBay', 'title': 'eBay Item'}
    elif 'bestbuy.' in domain:
        return {'store': 'Best Buy', 'title': 'Best Buy Product'}
    elif 'target.' in domain:
        return {'store': 'Target', 'title': 'Target Product'}
    elif 'walmart.' in domain:
        return {'store': 'Walmart', 'title': 'Walmart Product'}
    else:
        return {'store': 'Other', 'title': f'Product from {domain}'}

# ============================================================================
# Product Management Routes - WITH PREMIUM LIMIT CHECKING
# ============================================================================

@dashboard_bp.route('/api/products', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_user_products():
    """Get all products for the authenticated user"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        
        print(f"=== DEBUG GET_USER_PRODUCTS ===")
        print(f"User ID: {user_id} (type: {type(user_id)})")
        print(f"User ID String: '{user_id_str}' (type: {type(user_id_str)})")
        
        # Use the ENHANCED procedure with webhook data
        print(f"Attempting to call get_user_products_with_data...")
        try:
            result = Database.call_procedure('get_user_products_with_data', {
                'p_user_id': user_id
            })
            print(f"ENHANCED PROCEDURE RESULT: {result}")
            print(f"ENHANCED PROCEDURE RESULT TYPE: {type(result)}")
            if result:
                print(f"ENHANCED PROCEDURE RESULT LENGTH: {len(result)}")
                for i, row in enumerate(result):
                    print(f"  Row {i}: {row} (type: {type(row)})")
                    if hasattr(row, '__len__'):
                        print(f"    Row length: {len(row)}")
        except Exception as e:
            print(f"ENHANCED PROCEDURE FAILED: {e}")
            # Fallback to old procedure
            print(f"Falling back to get_user_products (old)...")
            try:
                result = Database.call_procedure('get_user_products', {
                    'p_user_id': user_id
                })
                print(f"OLD PROCEDURE RESULT: {result}")
            except Exception as e2:
                print(f"OLD PROCEDURE ALSO FAILED: {e2}")
                result = None
        
        if not result or len(result) == 0:
            print("No result or empty result - returning empty array")
            response = jsonify({'products': [], 'debug': 'No results found'})
            return add_cors_headers(response), 200
        
        print(f"\nProcessing result...")
        print(f"First row: {result[0]}")
        
        # Check if we got an error in first row
        first_row = result[0]
        if hasattr(first_row, '__len__') and len(first_row) > 0 and first_row[0] == 'error':
            print(f"Got error status: {first_row[1]}")
            response = jsonify({'error': first_row[1], 'products': [], 'debug': 'Error from procedure'})
            return add_cors_headers(response), 400
        
        # Parse products data
        products = []
        print(f"\nParsing {len(result)} rows...")
        
        for i, row in enumerate(result):
            print(f"\nProcessing row {i}: {row}")
            print(f"Row type: {type(row)}, length: {len(row) if hasattr(row, '__len__') else 'no length'}")
            
            # Skip status-only rows
            if hasattr(row, '__len__') and len(row) >= 2 and row[0] == 'success' and row[1] == 'Products retrieved successfully' and len(row) == 2:
                print(f"  Skipping status row: {row}")
                continue
            
            # Process rows that have the enhanced format (with webhooks)
            if hasattr(row, '__len__') and len(row) > 15:
                try:
                    # Enhanced procedure format with webhooks - FIXED COLUMN MAPPING
                    if row[0] == 'success' and len(row) > 15:
                        print(f"  Processing as ENHANCED procedure format with webhooks")
                        product = {
                            'id': row[2],
                            'url': row[3],
                            'title': row[4],
                            'store': row[5],
                            'current_price': float(row[6]) if row[6] else None,
                            'min_price_alert': float(row[7]) if row[7] else None,
                            'max_price_alert': float(row[8]) if row[8] else None,
                            'discord_webhook_url': row[9] if row[9] else '',
                            'alerts_sent': row[10] if row[10] else 0,
                            'status': row[11],  # FIXED: status is at index 11
                            'last_checked_at': row[12].isoformat() if row[12] else None,  # FIXED: moved from 11 to 12
                            'last_price_change': row[13].isoformat() if row[13] else None,  # FIXED: moved from 12 to 13
                            'sms_notifications_enabled': bool(row[14]) if row[14] is not None else False,  # NEW: SMS field
                            'created_at': row[15].isoformat() if row[15] else None,  # FIXED: moved from 14 to 15
                            'updated_at': row[16].isoformat() if row[16] else None,  # FIXED: moved from 15 to 16
                            'price_history_count': row[17] if len(row) > 17 else 0  # FIXED: moved from 16 to 17
                        }
                    else:
                        print(f"  Processing as enhanced format but different structure")
                        # Handle different enhanced format
                        product = {
                            'id': row[0],
                            'url': row[1],
                            'title': row[2],
                            'store': row[3],
                            'current_price': float(row[4]) if row[4] else None,
                            'min_price_alert': float(row[5]) if row[5] else None,
                            'max_price_alert': float(row[6]) if row[6] else None,
                            'discord_webhook_url': row[7] if len(row) > 7 and row[7] else '',
                            'status': row[8] if len(row) > 8 else 'checking',
                            'last_checked_at': row[9].isoformat() if len(row) > 9 and row[9] else None,
                            'last_price_change': row[10].isoformat() if len(row) > 10 and row[10] else None,
                            'alerts_sent': row[11] if len(row) > 11 and row[11] else 0,
                            'created_at': row[12].isoformat() if len(row) > 12 and row[12] else None,
                            'updated_at': row[13].isoformat() if len(row) > 13 and row[13] else None,
                            'price_history_count': row[14] if len(row) > 14 else 0
                        }
                    
                    products.append(product)
                    print(f"  Successfully added product: {product['title']} (ID: {product['id']})")
                    
                except (IndexError, TypeError, ValueError) as e:
                    print(f"  Error parsing row {i}: {e}")
                    print(f"  Row data: {row}")
                    continue
            elif hasattr(row, '__len__') and len(row) > 10:
                try:
                    # Old procedure format fallback
                    print(f"  Processing as OLD procedure format")
                    product = {
                        'id': row[0],
                        'url': row[1],
                        'title': row[2],
                        'store': row[3],
                        'current_price': float(row[4]) if row[4] else None,
                        'min_price_alert': float(row[5]) if row[5] else None,
                        'max_price_alert': float(row[6]) if row[6] else None,
                        'discord_webhook_url': '',  # Old procedure doesn't have this
                        'status': row[7],
                        'last_checked_at': row[8].isoformat() if row[8] else None,
                        'last_price_change': row[9].isoformat() if row[9] else None,
                        'alerts_sent': row[10] if row[10] else 0,
                        'created_at': row[11].isoformat() if row[11] else None,
                        'updated_at': row[12].isoformat() if row[12] else None,
                        'price_history_count': row[13] if len(row) > 13 else 0
                    }
                    
                    products.append(product)
                    print(f"  Successfully added product: {product['title']} (ID: {product['id']})")
                    
                except (IndexError, TypeError, ValueError) as e:
                    print(f"  Error parsing row {i}: {e}")
                    print(f"  Row data: {row}")
                    continue
            else:
                print(f"  Skipping row {i} - insufficient length or wrong format")
        
        print(f"\nFinal result: {len(products)} products parsed")
        for product in products:
            print(f"  - {product['title']} (ID: {product['id']})")
        
        response = jsonify({
            'products': products,
            'total_count': len(products),
            'debug': {
                'user_id': user_id,
                'result_length': len(result) if result else 0,
                'products_parsed': len(products)
            }
        })
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Get products error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        response = jsonify({
            'error': 'Failed to load products',
            'debug': str(e),
            'traceback': traceback.format_exc()
        })
        return add_cors_headers(response), 500

# MISSING ROUTE - ADD PRODUCT
@dashboard_bp.route('/api/products', methods=['POST', 'OPTIONS'])
@jwt_required()
def add_product():
    """Add a new product for tracking - WITH PREMIUM LIMIT CHECKING"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        data = request.get_json()
        
        print(f"=== DEBUG ADD_PRODUCT ===")
        print(f"User ID: {user_id}")
        print(f"Request data: {data}")
        
        if not data:
            response = jsonify({'error': 'No data provided'})
            return add_cors_headers(response), 400
        
        url = data.get('url', '').strip()
        title = data.get('title', '').strip()
        discord_webhook_url = data.get('discord_webhook_url', '').strip()
        sms_notifications_enabled = data.get('sms_notifications_enabled', False)
        
        if not url:
            response = jsonify({'error': 'Product URL is required'})
            return add_cors_headers(response), 400
        
        if not validate_url(url):
            response = jsonify({'error': 'Invalid URL format'})
            return add_cors_headers(response), 400
        
        # Validate Discord webhook URL if provided
        if discord_webhook_url and not (discord_webhook_url.startswith('https://discord.com/api/webhooks/') or 
                                      discord_webhook_url.startswith('https://discordapp.com/api/webhooks/')):
            response = jsonify({'error': 'Invalid Discord webhook URL format'})
            return add_cors_headers(response), 400
        
        # Extract product info if title not provided
        if not title:
            product_info = extract_product_info(url)
            title = product_info['title']
        
        print(f"Adding product: URL={url}, Title={title}, Discord={discord_webhook_url}, SMS={sms_notifications_enabled}")
        
        # Call the enhanced procedure with webhook and SMS support
        try:
            result = Database.call_procedure('add_user_product_with_webhook', {
                'p_user_id': user_id,
                'p_product_url': url,
                'p_product_title': title,
                'p_discord_webhook_url': discord_webhook_url if discord_webhook_url else None,
                'p_sms_notifications_enabled': sms_notifications_enabled
            })
            print(f"Enhanced add product result: {result}")
        except Exception as e:
            print(f"Enhanced add procedure failed: {e}")
            # Fall back to old procedure
            result = Database.call_procedure('add_user_product', {
                'p_user_id': user_id,
                'p_product_url': url,
                'p_product_title': title
            })
            print(f"Old add product result: {result}")
        
        if not result or len(result) == 0:
            response = jsonify({'error': 'Failed to add product'})
            return add_cors_headers(response), 500
        
        row = result[0]
        status = row[0]
        message = row[1]
        
        print(f"Add product status: {status}, message: {message}")
        
        if status != 'success':
            response = jsonify({'error': message})
            return add_cors_headers(response), 400
        
        # Get the new product ID if available
        product_id = row[2] if len(row) > 2 else None
        
        response = jsonify({
            'message': message,
            'product_id': product_id,
            'debug': {
                'user_id': user_id,
                'url': url,
                'title': title
            }
        })
        return add_cors_headers(response), 201
        
    except Exception as e:
        print(f"Add product error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        response = jsonify({'error': 'Failed to add product'})
        return add_cors_headers(response), 500

@dashboard_bp.route('/api/products/<int:product_id>', methods=['PUT', 'OPTIONS'])
@jwt_required()
def update_product(product_id):
    """Update product settings - WITH WEBHOOK SUPPORT"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        data = request.get_json()
        
        if not data:
            response = jsonify({'error': 'No data provided'})
            return add_cors_headers(response), 400
        
        min_price = data.get('min_price_alert')
        max_price = data.get('max_price_alert')
        discord_webhook = data.get('discord_webhook_url', '').strip()
        sms_notifications = data.get('sms_notifications_enabled')
        
        # Convert to float if provided
        min_price = float(min_price) if min_price is not None else None
        max_price = float(max_price) if max_price is not None else None
        
        # Use ENHANCED procedure with webhook support
        try:
            result = Database.call_procedure('update_user_product_with_webhook', {
                'p_user_id': user_id,
                'p_product_id': product_id,
                'p_min_price_alert': min_price,
                'p_max_price_alert': max_price,
                'p_discord_webhook_url': discord_webhook if discord_webhook else None,
                'p_sms_notifications_enabled': sms_notifications
            })
        except Exception as e:
            print(f"Enhanced update procedure failed: {e}")
            # Fall back to old procedure
            result = Database.call_procedure('update_user_product', {
                'p_user_id': user_id,
                'p_product_id': product_id,
                'p_min_price_alert': min_price,
                'p_max_price_alert': max_price
            })
        
        if not result or len(result) == 0:
            response = jsonify({'error': 'Failed to update product'})
            return add_cors_headers(response), 500
        
        row = result[0]
        status = row[0]
        message = row[1]
        
        if status != 'success':
            response = jsonify({'error': message})
            return add_cors_headers(response), 400
        
        response = jsonify({'message': message})
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Update product error: {str(e)}")
        response = jsonify({'error': 'Failed to update product'})
        return add_cors_headers(response), 500

@dashboard_bp.route('/api/products/<int:product_id>', methods=['DELETE', 'OPTIONS'])
@jwt_required()
def delete_product(product_id):
    """Delete a product"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        
        result = Database.call_procedure('delete_user_product', {
            'p_user_id': user_id,
            'p_product_id': product_id
        })
        
        if not result or len(result) == 0:
            response = jsonify({'error': 'Failed to delete product'})
            return add_cors_headers(response), 500
        
        row = result[0]
        status = row[0]
        message = row[1]
        
        if status != 'success':
            response = jsonify({'error': message})
            return add_cors_headers(response), 400
        
        response = jsonify({'message': message})
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Delete product error: {str(e)}")
        response = jsonify({'error': 'Failed to delete product'})
        return add_cors_headers(response), 500

# ============================================================================
# Dashboard API Routes
# ============================================================================

@dashboard_bp.route('/api/dashboard/overview', methods=['GET', 'OPTIONS'])
@jwt_required()
def dashboard_overview():
    """Get dashboard overview data"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        
        print(f"=== DEBUG DASHBOARD_OVERVIEW ===")
        print(f"User ID: {user_id}")
        
        # Use the enhanced procedure to get products
        try:
            products_result = Database.call_procedure('get_user_products_with_data', {
                'p_user_id': user_id
            })
            print(f"Dashboard overview - ENHANCED procedure result: {products_result}")
        except Exception as e:
            print(f"Dashboard overview - ENHANCED procedure failed: {e}")
            products_result = Database.call_procedure('get_user_products', {
                'p_user_id': user_id
            })
            print(f"Dashboard overview - OLD procedure result: {products_result}")
        
        if not products_result or len(products_result) == 0:
            response = jsonify({
                'user_name': 'User',
                'total_products': 0,
                'alerts_sent': 0,
                'restocks_found': 0,
                'money_saved': 0.0,
                'recent_activity': []
            })
            return add_cors_headers(response), 200
        
        # Parse the results similar to get_user_products
        products = []
        for row in products_result:
            if hasattr(row, '__len__') and len(row) >= 2 and row[0] == 'success' and row[1] == 'Products retrieved successfully' and len(row) == 2:
                continue  # Skip status row
                
            if hasattr(row, '__len__') and len(row) > 10:
                try:
                    if row[0] == 'success' and len(row) > 15:
                        # Enhanced procedure format - FIXED COLUMN MAPPING
                        product = {
                            'id': row[2],
                            'title': row[4],
                            'status': row[11],  # FIXED: status is at index 11
                            'alerts_sent': row[10] if row[10] else 0,  # FIXED: alerts_sent is at index 10
                            'created_at': row[15].isoformat() if row[15] else None,  # FIXED: created_at is at index 15
                        }
                    else:
                        # Old procedure format
                        product = {
                            'id': row[0],
                            'title': row[2],
                            'status': row[7],
                            'alerts_sent': row[10] if row[10] else 0,
                            'created_at': row[11].isoformat() if row[11] else None,
                        }
                    products.append(product)
                except (IndexError, TypeError) as e:
                    print(f"Error parsing dashboard product row: {e}")
                    continue
        
        # Calculate dashboard stats
        total_products = len(products)
        total_alerts = sum(product['alerts_sent'] for product in products)
        in_stock_count = sum(1 for product in products if product['status'] == 'in-stock')
        
        # Create recent activity from products
        recent_activity = []
        for product in products[:5]:  # Last 5 products
            activity = {
                'icon': 'fas fa-plus',
                'title': f'Added {product["title"]}',
                'time': product['created_at']
            }
            recent_activity.append(activity)
        
        # Get user info for name
        user_result = Database.call_procedure('get_user_by_id', {
            'p_user_id': user_id
        })
        
        user_name = 'User'
        if user_result and len(user_result) > 0 and user_result[0][0] == 'success':
            user_name = user_result[0][3]  # full_name column
        
        print(f"Dashboard stats - Products: {total_products}, Alerts: {total_alerts}, In Stock: {in_stock_count}")
        
        response = jsonify({
            'user_name': user_name,
            'total_products': total_products,
            'alerts_sent': total_alerts,
            'restocks_found': in_stock_count,
            'money_saved': 25.50,  # Placeholder for now
            'recent_activity': recent_activity
        })
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Dashboard overview error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        response = jsonify({'error': 'Failed to load dashboard data'})
        return add_cors_headers(response), 500

# ============================================================================
# Settings Routes
# ============================================================================

@dashboard_bp.route('/api/settings', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_user_settings():
    """Get user settings"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        
        result = Database.call_procedure('get_user_settings', {
            'p_user_id': user_id
        })
        
        if not result or len(result) == 0:
            response = jsonify({'error': 'Failed to load settings'})
            return add_cors_headers(response), 500
        
        # Check for error in result
        first_row = result[0]
        if hasattr(first_row, '__len__') and len(first_row) > 0 and first_row[0] == 'error':
            response = jsonify({'error': first_row[1]})
            return add_cors_headers(response), 400
        
        # Parse settings data (skip status message row)
        settings = {}
        for row in result:
            if hasattr(row, '__len__') and len(row) > 10:
                settings = {
                    'email_notifications': bool(row[0]) if row[0] is not None else True,
                    'discord_webhook_url': row[1] if row[1] else '',
                    'phone_number': row[2] if row[2] else '',
                    'sms_notifications': bool(row[3]) if row[3] is not None else False,
                    'notification_frequency': row[4] if row[4] else 'instant',
                    'price_drop_alerts': bool(row[5]) if row[5] is not None else True,
                    'restock_alerts': bool(row[6]) if row[6] is not None else True,
                    'price_increase_alerts': bool(row[7]) if row[7] is not None else False,
                    'dashboard_theme': row[8] if row[8] else 'light',
                    'items_per_page': row[9] if row[9] else 10,
                    'default_currency': row[10] if row[10] else 'USD',
                    'share_data': bool(row[11]) if row[11] is not None else False,
                    'public_profile': bool(row[12]) if row[12] is not None else False
                }
                break
        
        response = jsonify(settings)
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Get settings error: {str(e)}")
        response = jsonify({'error': 'Failed to load settings'})
        return add_cors_headers(response), 500

@dashboard_bp.route('/api/settings', methods=['PUT', 'OPTIONS'])
@jwt_required()
def update_user_settings():
    """Update user settings"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        data = request.get_json()
        
        if not data:
            response = jsonify({'error': 'No data provided'})
            return add_cors_headers(response), 400
        
        # Validate Discord webhook URL if provided
        discord_webhook = data.get('discord_webhook_url', '').strip()
        if discord_webhook and not (discord_webhook.startswith('https://discord.com/api/webhooks/') or 
                                  discord_webhook.startswith('https://discordapp.com/api/webhooks/')):
            response = jsonify({'error': 'Invalid Discord webhook URL format'})
            return add_cors_headers(response), 400
        
        # Update settings - NOW INCLUDING phone_number and sms_notifications
        result = Database.call_procedure('update_user_settings', {
            'p_user_id': user_id,
            'p_email_notifications': data.get('email_notifications'),
            'p_discord_webhook_url': discord_webhook or None,
            'p_notification_frequency': data.get('notification_frequency'),
            'p_price_drop_alerts': data.get('price_drop_alerts'),
            'p_restock_alerts': data.get('restock_alerts'),
            'p_price_increase_alerts': data.get('price_increase_alerts'),
            'p_dashboard_theme': data.get('dashboard_theme'),
            'p_items_per_page': data.get('items_per_page'),
            'p_default_currency': data.get('default_currency'),
            'p_share_data': data.get('share_data'),
            'p_public_profile': data.get('public_profile'),
            'p_phone_number': data.get('phone_number'),  # NEW: Position 13
            'p_sms_notifications': data.get('sms_notifications')  # NEW: Position 14
        })
        
        if not result or len(result) == 0:
            response = jsonify({'error': 'Failed to update settings'})
            return add_cors_headers(response), 500
        
        row = result[0]
        status = row[0]
        message = row[1]
        
        if status != 'success':
            response = jsonify({'error': message})
            return add_cors_headers(response), 400
        
        response = jsonify({'message': message})
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Update settings error: {str(e)}")
        response = jsonify({'error': 'Failed to update settings'})
        return add_cors_headers(response), 500