from flask import Blueprint, request, jsonify, session
from datetime import datetime, timezone
from models import db, Order, User, Listing, UserValidation
from services import discogs_service, auth_service

orders_api = Blueprint('orders_api', __name__)

@orders_api.route('/orders', methods=['GET'])
def get_orders():
    """Get all orders with user participation info"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    
    orders_data = []
    for order in orders:
        user_listings_count = Listing.query.filter_by(order_id=order.id, user_id=user.id).count()
        available_count = order.listings.filter_by(status='For Sale').count()

        print(f"DEBUG: Fetching seller info for {order.seller_name}")
        seller_info = discogs_service.fetch_seller_info(order.seller_name)
        print(f"DEBUG: Got seller info: {seller_info}")
        
        order_data = order.to_dict()
        order_data.update({
            'available_count': available_count,
            'user_listings_count': user_listings_count,
            'is_creator': order.creator_id == user.id,
            'is_participant': user_listings_count > 0,
            'seller_info': seller_info,
        })
        orders_data.append(order_data)
    
    return jsonify(orders_data)

@orders_api.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    """Get specific order with full details"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    return jsonify(order.to_dict(include_listings=True, current_user_id=current_user.id))

@orders_api.route('/orders/<int:order_id>/status', methods=['POST'])
def update_order_status(order_id):
    """Update order status (creator/admin only)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    new_status = data.get('status')
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    if order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Not authorized'}), 403
    
    valid_statuses = ['building', 'validation', 'ordered', 'delivered', 'closed']
    if new_status not in valid_statuses:
        return jsonify({'error': 'Invalid status'}), 400
    
    try:
        order.status = new_status
        order.status_changed_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({'success': True, 'status': new_status})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@orders_api.route('/orders/<int:order_id>/settings', methods=['POST'])
def update_order_settings(order_id):
    """Update order settings (creator/admin only)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    if order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Only creator can modify order settings'}), 403
    
    try:
        data = request.get_json()
        
        # Update order settings
        if 'direct_url' in data:
            order.direct_url = data['direct_url'].strip() if data['direct_url'] else None
        
        if 'max_amount' in data:
            order.max_amount = float(data['max_amount']) if data['max_amount'] else None
        
        if 'deadline' in data:
            if data['deadline']:
                try:
                    order.deadline = datetime.strptime(data['deadline'], '%Y-%m-%d')
                except ValueError:
                    return jsonify({'error': 'Invalid date format'}), 400
            else:
                order.deadline = None
        
        if 'payment_timing' in data:
            order.payment_timing = data['payment_timing']
        
        if 'shipping_cost' in data:
            order.shipping_cost = float(data['shipping_cost']) if data['shipping_cost'] else 0
        
        if 'taxes' in data:
            order.taxes = float(data['taxes']) if data['taxes'] else 0
        
        if 'discount' in data:
            discount_value = float(data['discount']) if data['discount'] else 0
            if discount_value < 0:
                return jsonify({'error': 'Le discount ne peut pas être négatif'}), 400
            if discount_value > order.total_with_fees:
                return jsonify({'error': 'Le discount ne peut pas être supérieur au total'}), 400
            order.discount = discount_value
        
        if 'seller_shop_url' in data:
            order.seller_shop_url = data['seller_shop_url'].strip() if data['seller_shop_url'] else None
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Paramètres mis à jour avec succès'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@orders_api.route('/orders/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    """Delete order (creator/admin only)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    if order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Only creator can delete order'}), 403
    
    try:
        db.session.delete(order)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Commande supprimée avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@orders_api.route('/orders/<int:order_id>/verify', methods=['POST'])
def verify_order_availability(order_id):
    """Verify availability of all listings in an order"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    
    verified_count = 0
    updated_count = 0
    unavailable_count = 0
    
    try:
        for listing in order.listings:
            try:
                listing_data = discogs_service.fetch_listing_data(listing.discogs_id)
                
                verified_count += 1
                old_status = listing.status
                
                listing.update_from_discogs_data(listing_data)
                
                if old_status != listing.status:
                    updated_count += 1
                    if listing.status != 'For Sale':
                        unavailable_count += 1
                        
            except Exception as e:
                if listing.status == 'For Sale':
                    listing.status = 'Not Available'
                    listing.last_checked = datetime.now(timezone.utc)
                    updated_count += 1
                    unavailable_count += 1
        
        db.session.commit()
        
        message = f"Vérification terminée: {verified_count} disques vérifiés"
        if updated_count > 0:
            message += f", {updated_count} mis à jour"
        if unavailable_count > 0:
            message += f", {unavailable_count} non-disponibles"
        
        return jsonify({
            'success': True,
            'message': message,
            'verified_count': verified_count,
            'updated_count': updated_count,
            'unavailable_count': unavailable_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@orders_api.route('/orders/<int:order_id>/validation-status', methods=['GET'])
def get_validation_status(order_id):
    """Get validation status for an order"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    # Check if current user has validated
    user_validation = UserValidation.query.filter_by(
        user_id=current_user.id, 
        order_id=order_id
    ).first()
    user_validated = user_validation.validated if user_validation else False
    
    # Get all validations for this order
    all_validations = UserValidation.query.filter_by(order_id=order_id).all()
    validations_data = [{
        'user_id': v.user_id,
        'validated': v.validated,
        'validated_at': v.validated_at.isoformat() if v.validated_at else None
    } for v in all_validations]
    
    return jsonify({
        'user_validated': user_validated,
        'all_validations': validations_data
    })

@orders_api.route('/orders/<int:order_id>/validate', methods=['POST'])
def validate_user_participation(order_id):
    """Validate user participation in an order"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    current_user = auth_service.get_current_user()
    
    try:
        validation = UserValidation.query.filter_by(
            user_id=current_user.id, 
            order_id=order_id
        ).first()
        
        if not validation:
            validation = UserValidation(user_id=current_user.id, order_id=order_id)
            db.session.add(validation)
        
        validation.validated = True
        validation.validated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({'success': True, 'validated': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@orders_api.route('/orders/<int:order_id>/user-summary', methods=['GET'])
def get_user_summary(order_id):
    """Get user summary for an order"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    summary = order.get_user_summary(current_user.id)
    
    return jsonify(summary)