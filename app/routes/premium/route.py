from flask import Blueprint, jsonify, request, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.db import Database
import stripe
import os
from datetime import datetime, timedelta
import json

premium_bp = Blueprint('premium', __name__)

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_...')  # Replace with your actual Stripe secret key

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

# ============================================================================
# Premium Subscription Routes
# ============================================================================

@premium_bp.route('/api/premium/subscription', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_user_subscription():
    """Get user's current subscription information"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        
        print(f"=== DEBUG GET_USER_SUBSCRIPTION ===")
        print(f"User ID: {user_id}")
        
        result = Database.call_procedure('get_user_subscription_info', {
            'p_user_id': user_id
        })
        
        print(f"Subscription result: {result}")
        
        if not result or len(result) == 0:
            # Return default free subscription info
            response = jsonify({
                'subscription': {
                    'subscription_id': None,
                    'plan_name': 'Free Plan',
                    'plan_type': 'free',
                    'price_per_month': 0.00,
                    'max_products': 2,
                    'subscription_status': 'active',
                    'current_products_count': 0,
                    'has_ai_enhancement': False,
                    'current_period_start': None,
                    'current_period_end': None,
                    'cancel_at_period_end': False
                }
            })
            return add_cors_headers(response), 200
        
        # Check for error in result
        first_row = result[0]
        if hasattr(first_row, '__len__') and len(first_row) > 0 and first_row[0] == 'error':
            response = jsonify({'error': first_row[1]})
            return add_cors_headers(response), 400
        
        # Parse subscription data with CORRECT column indexing
        # The procedure returns: status(0), message(1), then data starting at index 2
        subscription_data = None
        for row in result:
            if hasattr(row, '__len__') and len(row) > 15:
                print(f"Parsing subscription row: {row}")
                
                # FIXED: Account for status and message columns at the beginning
                subscription_data = {
                    'subscription_id': row[2],   # was row[0] - FIXED
                    'plan_name': row[3],         # was row[1] - FIXED  
                    'plan_type': row[4],         # was row[2] - FIXED
                    'price_per_month': float(row[5]) if row[5] is not None else 0.00,  # was row[3] - THIS WAS THE BUG!
                    'price_per_product': float(row[6]) if row[6] is not None else None,  # was row[4] - FIXED
                    'max_products': row[7] if row[7] is not None else 2,  # was row[5] - FIXED
                    'subscription_status': row[8],  # was row[6] - FIXED
                    'current_period_start': row[9].isoformat() if row[9] else None,  # was row[7] - FIXED
                    'current_period_end': row[10].isoformat() if row[10] else None,  # was row[8] - FIXED
                    'cancel_at_period_end': bool(row[11]) if row[11] is not None else False,  # was row[9] - FIXED
                    'stripe_customer_id': row[12],  # was row[10] - FIXED
                    'stripe_subscription_id': row[13],  # was row[11] - FIXED
                    'current_products_count': row[14] if row[14] else 0,  # was row[12] - FIXED
                    'has_ai_enhancement': bool(row[15]) if row[15] is not None else False  # was row[13] - FIXED
                }
                print(f"Successfully parsed subscription data: {subscription_data}")
                break
        
        if not subscription_data:
            # Return default free subscription
            subscription_data = {
                'subscription_id': None,
                'plan_name': 'Free Plan',
                'plan_type': 'free',
                'price_per_month': 0.00,
                'max_products': 2,
                'subscription_status': 'active',
                'current_products_count': 0,
                'has_ai_enhancement': False,
                'current_period_start': None,
                'current_period_end': None,
                'cancel_at_period_end': False
            }
        
        response = jsonify({'subscription': subscription_data})
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Get subscription error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        response = jsonify({'error': 'Failed to load subscription information'})
        return add_cors_headers(response), 500

@premium_bp.route('/api/premium/check-limit', methods=['GET', 'OPTIONS'])
@jwt_required()
def check_product_limit():
    """Check if user can add more products"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        
        result = Database.call_procedure('check_product_limit', {
            'p_user_id': user_id
        })
        
        if not result or len(result) == 0:
            response = jsonify({'error': 'Failed to check product limit'})
            return add_cors_headers(response), 500
        
        row = result[0]
        status = row[0]
        message = row[1]
        can_add = bool(row[2]) if len(row) > 2 else False
        current_count = row[3] if len(row) > 3 else 0
        max_allowed = row[4] if len(row) > 4 else 2
        plan_type = row[5] if len(row) > 5 else 'free'
        
        if status != 'success':
            response = jsonify({'error': message})
            return add_cors_headers(response), 400
        
        response = jsonify({
            'can_add_product': can_add,
            'current_count': current_count,
            'max_allowed': max_allowed,
            'plan_type': plan_type
        })
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Check limit error: {str(e)}")
        response = jsonify({'error': 'Failed to check product limit'})
        return add_cors_headers(response), 500

@premium_bp.route('/api/premium/plans', methods=['GET', 'OPTIONS'])
def get_subscription_plans():
    """Get all available subscription plans and add-ons"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        result = Database.call_procedure('get_all_subscription_plans', {})
        
        if not result or len(result) == 0:
            response = jsonify({'error': 'Failed to load subscription plans'})
            return add_cors_headers(response), 500
        
        # Check for error in result
        first_row = result[0]
        if hasattr(first_row, '__len__') and len(first_row) > 0 and first_row[0] == 'error':
            response = jsonify({'error': first_row[1]})
            return add_cors_headers(response), 400
        
        plans = []
        addons = []
        reading_addons = False
        
        for row in result:
            if hasattr(row, '__len__') and len(row) >= 2:
                # Skip status messages
                if row[0] == 'success' and len(row) == 2:
                    continue
                
                # Check if this looks like a plan or addon based on column count
                if len(row) >= 8 and not reading_addons:  # Plan format
                    plan = {
                        'id': row[0],
                        'plan_name': row[1],
                        'plan_type': row[2],
                        'price_per_month': float(row[3]) if row[3] else 0.00,
                        'price_per_product': float(row[4]) if row[4] else None,
                        'max_products': row[5],
                        'stripe_price_id': row[6],
                        'is_active': bool(row[7])
                    }
                    plans.append(plan)
                elif len(row) >= 6:  # Addon format
                    reading_addons = True
                    addon = {
                        'id': row[0],
                        'addon_name': row[1],
                        'addon_description': row[2],
                        'price_per_month': float(row[3]) if row[3] else 0.00,
                        'stripe_price_id': row[4],
                        'is_active': bool(row[5])
                    }
                    addons.append(addon)
        
        response = jsonify({
            'plans': plans,
            'addons': addons
        })
        return add_cors_headers(response), 200
        
    except Exception as e:
        print(f"Get plans error: {str(e)}")
        response = jsonify({'error': 'Failed to load subscription plans'})
        return add_cors_headers(response), 500

@premium_bp.route('/api/premium/create-checkout-session', methods=['POST', 'OPTIONS'])
@jwt_required()
def create_checkout_session():
    """Create Stripe checkout session for subscription"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        data = request.get_json()
        
        if not data:
            response = jsonify({'error': 'No data provided'})
            return add_cors_headers(response), 400
        
        plan_type = data.get('plan_type')
        custom_product_count = data.get('custom_product_count')
        include_ai_enhancement = data.get('include_ai_enhancement', False)
        
        print(f"=== DEBUG CREATE_CHECKOUT_SESSION ===")
        print(f"User ID: {user_id}")
        print(f"Plan type: {plan_type}")
        print(f"Custom product count: {custom_product_count}")
        print(f"Include AI enhancement: {include_ai_enhancement}")
        
        if not plan_type:
            response = jsonify({'error': 'Plan type is required'})
            return add_cors_headers(response), 400
        
        # Get user email for Stripe customer
        user_result = Database.call_procedure('get_user_by_id', {
            'p_user_id': user_id
        })
        
        user_email = 'user@example.com'  # Default
        if user_result and len(user_result) > 0 and user_result[0][0] == 'success':
            user_email = user_result[0][2]  # email column
        
        # Create or get Stripe customer
        try:
            customer = stripe.Customer.create(
                email=user_email,
                metadata={'user_id': str(user_id)}
            )
        except stripe.error.StripeError as e:
            print(f"Stripe customer creation error: {e}")
            # Try to find existing customer
            customers = stripe.Customer.list(email=user_email, limit=1)
            if customers.data:
                customer = customers.data[0]
            else:
                response = jsonify({'error': 'Failed to create Stripe customer'})
                return add_cors_headers(response), 500
        
        # Build line items based on plan type
        line_items = []
        
        if plan_type == 'pay_as_you_go':
            if not custom_product_count or custom_product_count < 1:
                response = jsonify({'error': 'Product count is required for pay-as-you-go plan'})
                return add_cors_headers(response), 400
            
            # Calculate price: $5 per product per month
            total_price = custom_product_count * 5.00
            
            # Create a price for this custom amount
            price = stripe.Price.create(
                unit_amount=int(total_price * 100),  # Convert to cents
                currency='usd',
                recurring={'interval': 'month'},
                product_data={
                    'name': f'Pay-as-you-go Plan ({custom_product_count} products)',
                    'description': f'Track up to {custom_product_count} products'
                }
            )
            
            line_items.append({
                'price': price.id,
                'quantity': 1
            })
            
        elif plan_type == 'unlimited':
            # Create unlimited plan price
            price = stripe.Price.create(
                unit_amount=14500,  # $145.00 in cents
                currency='usd',
                recurring={'interval': 'month'},
                product_data={
                    'name': 'Unlimited Access Plan',
                    'description': 'Track unlimited products'
                }
            )
            
            line_items.append({
                'price': price.id,
                'quantity': 1
            })
        else:
            response = jsonify({'error': 'Invalid plan type'})
            return add_cors_headers(response), 400
        
        # Add AI enhancement if requested
        if include_ai_enhancement:
            ai_price = stripe.Price.create(
                unit_amount=5000,  # $50.00 in cents
                currency='usd',
                recurring={'interval': 'month'},
                product_data={
                    'name': 'AI Enhancement Add-on',
                    'description': 'Advanced AI-powered tracking with multiple failsafe layers'
                }
            )
            
            line_items.append({
                'price': ai_price.id,
                'quantity': 1
            })
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=line_items,
            mode='subscription',
            success_url=f"{request.host_url}dashboard/premium?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{request.host_url}dashboard/premium",
            metadata={
                'user_id': str(user_id),
                'plan_type': plan_type,
                'custom_product_count': str(custom_product_count) if custom_product_count else '',
                'include_ai_enhancement': str(include_ai_enhancement)
            }
        )
        
        response = jsonify({
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id
        })
        return add_cors_headers(response), 200
        
    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        response = jsonify({'error': f'Payment processing error: {str(e)}'})
        return add_cors_headers(response), 400
    except Exception as e:
        print(f"Create checkout session error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        response = jsonify({'error': 'Failed to create checkout session'})
        return add_cors_headers(response), 500

@premium_bp.route('/api/premium/process-success', methods=['POST', 'OPTIONS'])
@jwt_required()
def process_checkout_success():
    """Process successful checkout and update user subscription"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        data = request.get_json()
        
        if not data or not data.get('session_id'):
            response = jsonify({'error': 'Session ID is required'})
            return add_cors_headers(response), 400
        
        session_id = data.get('session_id')
        
        # Retrieve the checkout session
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status != 'paid':
            response = jsonify({'error': 'Payment was not successful'})
            return add_cors_headers(response), 400
        
        # Get subscription details
        subscription = stripe.Subscription.retrieve(session.subscription)
        
        plan_type = session.metadata.get('plan_type')
        custom_product_count = session.metadata.get('custom_product_count')
        include_ai_enhancement = session.metadata.get('include_ai_enhancement') == 'True'
        
        custom_product_count = int(custom_product_count) if custom_product_count and custom_product_count.isdigit() else None
        
        # Convert timestamps
        period_start = datetime.fromtimestamp(subscription.current_period_start)
        period_end = datetime.fromtimestamp(subscription.current_period_end)
        
        # Create user subscription in database
        result = Database.call_procedure('create_user_subscription', {
            'p_user_id': user_id,
            'p_plan_type': plan_type,
            'p_custom_product_limit': custom_product_count,
            'p_stripe_customer_id': session.customer,
            'p_stripe_subscription_id': subscription.id,
            'p_stripe_session_id': session_id,
            'p_period_start': period_start,
            'p_period_end': period_end
        })
        
        if not result or len(result) == 0:
            response = jsonify({'error': 'Failed to create subscription'})
            return add_cors_headers(response), 500
        
        row = result[0]
        status = row[0]
        message = row[1]
        subscription_id = row[2] if len(row) > 2 else None
        
        if status != 'success':
            response = jsonify({'error': message})
            return add_cors_headers(response), 400
        
        # Add AI enhancement addon if requested
        if include_ai_enhancement and subscription_id:
            try:
                Database.call_procedure('add_subscription_addon', {
                    'p_subscription_id': subscription_id,
                    'p_addon_name': 'AI Enhancement',
                    'p_stripe_subscription_item_id': subscription.items.data[-1].id if subscription.items.data else None
                })
            except Exception as e:
                print(f"Failed to add AI enhancement addon: {e}")
        
        # Record payment
        try:
            total_amount = sum(item.price.unit_amount for item in subscription.items.data) / 100.0
            
            # Insert payment history (this would need a new procedure)
            # Database.call_procedure('record_payment', {
            #     'p_user_id': user_id,
            #     'p_subscription_id': subscription_id,
            #     'p_stripe_payment_intent_id': session.payment_intent,
            #     'p_amount': total_amount,
            #     'p_payment_status': 'succeeded',
            #     'p_description': f'Subscription: {plan_type}'
            # })
        except Exception as e:
            print(f"Failed to record payment: {e}")
        
        response = jsonify({
            'message': 'Subscription created successfully',
            'subscription_id': subscription_id
        })
        return add_cors_headers(response), 200
        
    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        response = jsonify({'error': f'Payment verification error: {str(e)}'})
        return add_cors_headers(response), 400
    except Exception as e:
        print(f"Process success error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        response = jsonify({'error': 'Failed to process subscription'})
        return add_cors_headers(response), 500

@premium_bp.route('/api/premium/cancel', methods=['POST', 'OPTIONS'])
@jwt_required()
def cancel_subscription():
    """Cancel user's subscription"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        data = request.get_json()
        
        cancel_immediately = data.get('cancel_immediately', False) if data else False
        
        # Get user's current subscription
        subscription_result = Database.call_procedure('get_user_subscription_info', {
            'p_user_id': user_id
        })
        
        stripe_subscription_id = None
        for row in subscription_result:
            if hasattr(row, '__len__') and len(row) > 13:
                stripe_subscription_id = row[13]  # FIXED: was row[11], now row[13] for stripe_subscription_id
                break
        
        # Cancel in Stripe if subscription exists
        if stripe_subscription_id:
            try:
                if cancel_immediately:
                    stripe.Subscription.delete(stripe_subscription_id)
                else:
                    stripe.Subscription.modify(
                        stripe_subscription_id,
                        cancel_at_period_end=True
                    )
            except stripe.error.StripeError as e:
                print(f"Stripe cancellation error: {e}")
                # Continue with database update even if Stripe fails
        
        # Update in database
        result = Database.call_procedure('cancel_user_subscription', {
            'p_user_id': user_id,
            'p_cancel_immediately': cancel_immediately
        })
        
        if not result or len(result) == 0:
            response = jsonify({'error': 'Failed to cancel subscription'})
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
        print(f"Cancel subscription error: {str(e)}")
        response = jsonify({'error': 'Failed to cancel subscription'})
        return add_cors_headers(response), 500

@premium_bp.route('/api/premium/update', methods=['PUT', 'OPTIONS'])
@jwt_required()
def update_subscription():
    """Update user's subscription (change plan, product count, etc.)"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        user_id_str = get_jwt_identity()
        user_id = int(user_id_str)
        data = request.get_json()
        
        if not data:
            response = jsonify({'error': 'No data provided'})
            return add_cors_headers(response), 400
        
        # This would involve creating a new checkout session for the updated plan
        # and canceling the current subscription - similar to create_checkout_session
        # but with modification logic
        
        response = jsonify({'message': 'Subscription update functionality not yet implemented'})
        return add_cors_headers(response), 501
        
    except Exception as e:
        print(f"Update subscription error: {str(e)}")
        response = jsonify({'error': 'Failed to update subscription'})
        return add_cors_headers(response), 500

# ============================================================================
# Stripe Webhook Handler
# ============================================================================

@premium_bp.route('/api/premium/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_...')  # Replace with your webhook secret
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        print("Invalid payload")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        print("Invalid signature")
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        print(f"Checkout session completed: {session['id']}")
        # Additional processing if needed
        
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        print(f"Subscription updated: {subscription['id']}")
        # Update subscription status in database
        
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        print(f"Subscription cancelled: {subscription['id']}")
        # Handle subscription cancellation
        
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        print(f"Payment failed: {invoice['id']}")
        # Handle failed payment
        
    else:
        print(f"Unhandled event type: {event['type']}")
    
    return jsonify({'status': 'success'}), 200