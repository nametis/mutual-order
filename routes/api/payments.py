from flask import Blueprint, jsonify, request
from models import db
from models.order import Order
from models.payment import UserPayment
from services import auth_service

payments_api = Blueprint('payments_api', __name__)

@payments_api.route('/orders/<int:order_id>/payments', methods=['GET'])
def get_order_payments(order_id):
    """Get all payment records for an order (creator/admin only)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    # Only creator or admin can view all payments
    if order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    payments = UserPayment.query.filter_by(order_id=order_id).all()
    
    # If no payments exist, initialize them
    if not payments and order.creator_id == current_user.id:
        # Call initialize endpoint logic
        try:
            participants_summary = order.get_all_participants_summary()
            
            for user_id, data in participants_summary.items():
                user_total = data['summary']['total']
                
                payment = UserPayment(
                    order_id=order_id,
                    user_id=user_id,
                    amount_due=user_total
                )
                db.session.add(payment)
            
            db.session.commit()
            
            # Reload payments
            payments = UserPayment.query.filter_by(order_id=order_id).all()
        except Exception as e:
            print(f"Error initializing payments: {e}")
    
    return jsonify([payment.to_dict() for payment in payments])

@payments_api.route('/orders/<int:order_id>/payments/my-status', methods=['GET'])
def get_my_payment_status(order_id):
    """Get current user's payment status for an order"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    payment = UserPayment.query.filter_by(
        order_id=order_id,
        user_id=current_user.id
    ).first()
    
    if not payment:
        return jsonify({'error': 'No payment record found'}), 404
    
    return jsonify(payment.to_dict())

@payments_api.route('/orders/<int:order_id>/payments/<int:payment_id>/mark-paid', methods=['POST'])
def mark_payment_paid(order_id, payment_id):
    """Mark a payment as paid (creator/admin only)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        order = Order.query.get_or_404(order_id)
        current_user = auth_service.get_current_user()
        
        # Only creator or admin can mark payments
        if order.creator_id != current_user.id and not current_user.is_admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        payment = UserPayment.query.get_or_404(payment_id)
        if payment.order_id != order_id:
            return jsonify({'error': 'Payment does not belong to this order'}), 400
        
        # Try to get JSON data, but don't require it
        try:
            data = request.get_json() if request.content_type and 'application/json' in request.content_type else {}
        except:
            data = {}
        
        payment.mark_as_paid(
            amount=data.get('amount_paid') if data else payment.amount_due,
            payment_reference=data.get('payment_reference') if data else None,
            notes=data.get('notes') if data else None
        )
        
        db.session.commit()
        return jsonify({'success': True, 'payment': payment.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@payments_api.route('/orders/<int:order_id>/payments/<int:payment_id>/unmark-paid', methods=['POST'])
def unmark_payment_paid(order_id, payment_id):
    """Unmark a payment as paid (creator/admin only)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        order = Order.query.get_or_404(order_id)
        current_user = auth_service.get_current_user()
        
        # Only creator or admin can unmark payments
        if order.creator_id != current_user.id and not current_user.is_admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        payment = UserPayment.query.get_or_404(payment_id)
        if payment.order_id != order_id:
            return jsonify({'error': 'Payment does not belong to this order'}), 400
        
        payment.is_paid = False
        payment.paid_at = None
        db.session.commit()
        
        return jsonify({'success': True, 'payment': payment.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@payments_api.route('/orders/<int:order_id>/initialize-payments', methods=['POST'])
def initialize_payments(order_id):
    """Initialize payment records for all participants (creator/admin only)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    # Only creator or admin can initialize payments
    if order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get participants and their summaries
    participants_summary = order.get_all_participants_summary()
    
    # Create or update payment records for each participant
    for user_id, data in participants_summary.items():
        payment = UserPayment.query.filter_by(
            order_id=order_id,
            user_id=user_id
        ).first()
        
        user_total = data['summary']['total']
        
        if payment:
            # Update existing payment
            payment.amount_due = user_total
            payment.updated_at = db.session.query(db.func.now()).scalar()
        else:
            # Create new payment
            payment = UserPayment(
                order_id=order_id,
                user_id=user_id,
                amount_due=user_total
            )
            db.session.add(payment)
    
    db.session.commit()
    
    # Get updated payments
    payments = UserPayment.query.filter_by(order_id=order_id).all()
    return jsonify({
        'success': True,
        'payments': [payment.to_dict() for payment in payments]
    })

