from flask import Blueprint, json, jsonify, request, redirect, url_for
from sqlalchemy import text
import stripe
from app import db
from app.utils.db import Database
import os
from datetime import datetime

donation_bp = Blueprint('donation', __name__)

stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

@donation_bp.route("/create-session", methods=['POST', 'OPTIONS'])
def create_donation_session():
    """Create a Stripe checkout session for one-time donations"""
    if request.method == 'OPTIONS':
        return handle_preflight()
        
    try:
        data = request.get_json()
        amount = int(data['amount'])  # Amount in dollars
        donor_name = data.get('name', '')
        donor_email = data.get('email', '')
        
        # Validate amount (minimum $1)
        if amount < 1:
            raise ValueError("Donation amount must be at least $1")
            
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        
        # Create checkout session for one-time payment
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': amount * 100,  # Convert to cents
                    'product_data': {
                        'name': 'Donation to Playbox Productions',
                        'description': 'Supporting transformative theater experiences',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',  # One-time payment, not subscription
            success_url=request.host_url + 'donation/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url + 'donations',
            metadata={
                'donor_name': donor_name,
                'donor_email': donor_email,
                'donation_amount': amount,
                'donation_type': 'one_time'
            },
            customer_email=donor_email if donor_email else None,
            allow_promotion_codes=True,
        )

        if session and session.id:
            response = jsonify({
                'sessionId': session.id,
                'url': session.url
            })
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
        response = jsonify({'error': f'Internal server error: {str(e)}'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@donation_bp.route("/success")
def donation_success():
    """Handle successful donation redirect"""
    session_id = request.args.get('session_id')
    
    if not session_id:
        return redirect(url_for('main.donations'))
    
    try:
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status == 'paid':
            # Get donation details from metadata
            donor_name = session.metadata.get('donor_name', 'Anonymous')
            donor_email = session.metadata.get('donor_email', '')
            amount = session.metadata.get('donation_amount', '0')
            
            # Save to database
            result = Database.call_procedure('save_donation', {
                'p_session_id': session_id,
                'p_donor_name': donor_name,
                'p_donor_email': donor_email,
                'p_amount': float(amount),
                'p_stripe_payment_intent': session.payment_intent,
                'p_status': 'completed'
            })
            
            if result and len(result) > 0:
                row = result[0]
                if row[0] == 'success':
                    # Return success page with donation details
                    return f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Thank You - Playbox Productions</title>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <style>
                            body {{ 
                                font-family: Arial, sans-serif; 
                                text-align: center; 
                                padding: 50px; 
                                background: #f8f8f8;
                            }}
                            .success-container {{
                                background: white;
                                padding: 40px;
                                border-radius: 16px;
                                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                                max-width: 600px;
                                margin: 0 auto;
                            }}
                            .success-icon {{ 
                                font-size: 60px; 
                                color: #27ae60; 
                                margin-bottom: 20px; 
                            }}
                            .amount {{ 
                                font-size: 36px; 
                                font-weight: bold; 
                                color: #e74c3c; 
                                margin: 20px 0; 
                            }}
                            .btn {{
                                background: #455a74;
                                color: white;
                                padding: 12px 24px;
                                text-decoration: none;
                                border-radius: 8px;
                                display: inline-block;
                                margin-top: 20px;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="success-container">
                            <div class="success-icon">✅</div>
                            <h1>Thank You for Your Donation!</h1>
                            <div class="amount">${amount}</div>
                            <p>Dear {donor_name},</p>
                            <p>Your generous donation has been successfully processed. You will receive an email confirmation shortly.</p>
                            <p>Your support helps us continue creating transformative theater experiences that inspire and connect our community.</p>
                            <a href="/" class="btn">Return to Home</a>
                        </div>
                    </body>
                    </html>
                    """
                else:
                    return f"Error saving donation: {row[1]}", 500
            else:
                return "Error processing donation", 500
        else:
            return redirect(url_for('main.donations') + '?error=payment_failed')
            
    except Exception as e:
        print(f"Error in donation success: {str(e)}")
        return redirect(url_for('main.donations') + '?error=processing_error')

@donation_bp.route('/webhook', methods=['POST', 'OPTIONS'])
def handle_donation_webhook():
    """Handle Stripe webhooks for donation events"""
    if request.method == 'OPTIONS':
        return handle_preflight()

    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_webhook_secret
        )

        # Handle successful payment
        if event.type == 'checkout.session.completed':
            session = event.data.object
            
            # Only process if it's a donation (not subscription)
            if session.mode == 'payment' and session.metadata.get('donation_type') == 'one_time':
                print("Processing donation webhook - values:", {
                    'session_id': session.id,
                    'donor_name': session.metadata.get('donor_name'),
                    'donor_email': session.metadata.get('donor_email'),
                    'amount': session.metadata.get('donation_amount'),
                    'payment_intent': session.payment_intent,
                    'status': 'completed'
                })
                
                # Save donation to database
                result = Database.call_procedure('save_donation', {
                    'p_session_id': session.id,
                    'p_donor_name': session.metadata.get('donor_name', 'Anonymous'),
                    'p_donor_email': session.metadata.get('donor_email', ''),
                    'p_amount': float(session.metadata.get('donation_amount', 0)),
                    'p_stripe_payment_intent': session.payment_intent,
                    'p_status': 'completed'
                })
                
                if result and len(result) > 0:
                    row = result[0]
                    if row[0] != 'success':
                        print(f"Failed to save donation: {row[1]}")
                        return jsonify({'error': row[1]}), 500
                else:
                    print("Procedure returned no data")
                    return jsonify({'error': 'No results returned'}), 500

        # Handle payment failure
        elif event.type == 'checkout.session.async_payment_failed':
            session = event.data.object
            
            if session.mode == 'payment' and session.metadata.get('donation_type') == 'one_time':
                result = Database.call_procedure('update_donation_status', {
                    'p_session_id': session.id,
                    'p_status': 'failed'
                })
                
                if result and len(result) > 0:
                    row = result[0]
                    if row[0] != 'success':
                        print(f"Failed to update donation status: {row[1]}")

        response = jsonify({'status': 'success'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200

    except stripe.error.SignatureVerificationError as e:
        print(f"Invalid signature: {str(e)}")
        response = jsonify({'error': 'Invalid signature'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 400
    except Exception as e:
        print(f"Error processing donation webhook: {str(e)}")
        response = jsonify({'error': str(e)})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@donation_bp.route('/admin/donations', methods=['GET'])
def get_donations():
    """Admin endpoint to retrieve donation records"""
    try:
        result = Database.call_procedure('get_all_donations', {})
        
        if result:
            donations = []
            for row in result:
                donations.append({
                    'id': row[0],
                    'donor_name': row[1],
                    'donor_email': row[2],
                    'amount': float(row[3]),
                    'status': row[4],
                    'created_at': row[5].isoformat() if row[5] else None,
                    'session_id': row[6]
                })
            
            response = jsonify({
                'status': 'success',
                'donations': donations,
                'total_donations': len(donations),
                'total_amount': sum(d['amount'] for d in donations if d['status'] == 'completed')
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response
        else:
            response = jsonify({'status': 'success', 'donations': [], 'total_donations': 0, 'total_amount': 0})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response
            
    except Exception as e:
        response = jsonify({'error': str(e)})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

def handle_preflight():
    """Handle CORS preflight requests"""
    response = jsonify({'message': 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response, 200