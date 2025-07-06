from flask import Blueprint, json, jsonify, request
from sqlalchemy import text
import stripe
from app import db
from app.utils.db import Database
import os 

stripe_bp = Blueprint('stripe', __name__)


stripe_webhook = os.getenv("STRIPE_WEBHOOK_SECRET")

stripe_monthly_price = os.getenv("STRIPE_MONTHLY")
stripe_yearly_price = os.getenv("STRIPE_YEARLY")
    
@stripe_bp.route("/request", methods=['GET', 'POST', 'OPTIONS'])
def create_payment():
    if request.method == 'OPTIONS':
        return handle_preflight()
        
    data = request.get_json()
    amount = data['amount']
    server_id = data['serverID']

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    try:
        if amount == "500":
            price_id = stripe_monthly_price
            subscription_type = 'monthly'
        elif amount == "5000":
            price_id = stripe_yearly_price
            subscription_type = 'yearly'
        else:
            raise ValueError(f"Invalid subscription amount of {amount}")

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': int(amount),
                    'product_data': {
                        'name': f'Server {server_id} Premium',
                    },
                    'recurring': {
                        'interval': 'month' if amount == "500" else 'year',
                    },
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url='http://interly.net/premium-new',
            cancel_url='http://interly.net/',
            subscription_data={  # Add subscription metadata
                'metadata': {
                    'server_id': server_id,
                    'subscription_type': subscription_type,
                }
            },
            metadata={  # Session metadata
                'server_id': server_id,
                'subscription_type': subscription_type,
            },
                allow_promotion_codes=True,
        )

        if session and session.id:
            response = jsonify({'sessionId': session.id})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response
        else:
            response = jsonify({'error': 'Failed to create checkout session'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400

    except ValueError as e:
        response = jsonify({'error': str(e)})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    except Exception as e:
        response = jsonify({'error': str(e)})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 403

@stripe_bp.route('/webhook', methods=['POST', 'OPTIONS'])
def handle_webhook():
    if request.method == 'OPTIONS':
        return handle_preflight()

    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )

        # Handle subscription creation
        if event.type == 'customer.subscription.created':
            subscription = event.data.object
            
            print("Before calling procedure - values:", {
                'server_id': subscription.metadata.get('server_id'),
                'subscription_id': subscription.id,
                'subscription_type': subscription.metadata.get('subscription_type'),
                'status': subscription.status,
                'expires_at': subscription.current_period_end
            })
            
            result = Database.call_procedure('add_server_premium', {
                'p_server_id': subscription.metadata.get('server_id'),
                'p_subscription_id': subscription.id,
                'p_subscription_type': subscription.metadata.get('subscription_type'),
                'p_status': subscription.status,
                'p_expires_at': subscription.current_period_end
            })
            
            print("After procedure call - Result:", result)
            if not result or len(result) == 0:
                print("Procedure returned no data")
                return jsonify({'error': 'No results returned'}), 500
                
            row = result[0]
            print("Procedure return values:", row)
            
            if row[0] != 'success':
                print(f"Failed to add premium status: {row[1]}")
                return jsonify({'error': row[1]}), 500

            # After successful update, verify the database state
            verify_result = Database.call_procedure('check_premium_status_via_dashboard', {
                'p_disc_guild_id': subscription.metadata.get('server_id')
            })
            print("Verification result:", verify_result)

        # Handle subscription updates
        elif event.type == 'customer.subscription.updated':
            subscription = event.data.object
            
            result = Database.call_procedure('update_server_premium', {
                'p_server_id': subscription.metadata.get('server_id'),
                'p_subscription_id': subscription.id,
                'p_status': subscription.status,
                'p_expires_at': subscription.current_period_end
            })
            
            if not result or len(result) == 0:
                print("Procedure returned no data")
                return jsonify({'error': 'No results returned'}), 500
                
            row = result[0]
            if row[0] != 'success':
                print(f"Failed to update premium status: {row[1]}")
                return jsonify({'error': row[1]}), 500

        # Handle subscription deletion
        elif event.type == 'customer.subscription.deleted':
            subscription = event.data.object
            
            result = Database.call_procedure('delete_server_premium', {
                'p_subscription_id': subscription.id
            })
            
            if not result or len(result) == 0:
                print("Procedure returned no data")
                return jsonify({'error': 'No results returned'}), 500
                
            row = result[0]
            if row[0] != 'success':
                print(f"Failed to delete premium status: {row[1]}")
                return jsonify({'error': row[1]}), 500

        response = jsonify({'status': 'success'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200

    except stripe.error.SignatureVerificationError as e:
        print(f"Invalid signature: {str(e)}")
        response = jsonify({'error': 'Invalid signature'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        response = jsonify({'error': str(e)})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500
    
def handle_preflight():
    response = jsonify({'message': 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response, 200