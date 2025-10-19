from flask import Blueprint, request, jsonify, session
from datetime import datetime, timezone
from models import db, Order, User, Listing, UserValidation, WantlistItem
from services import discogs_service, auth_service, wantlist_matching_service, cache_service

orders_api = Blueprint('orders_api', __name__)

@orders_api.route('/orders', methods=['GET'])
def get_orders():
    """Get orders with user participation info - heavily cached for performance"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    
    # Check cache first
    cache_key = f"dashboard_orders_{user.id}_{user.is_admin}"
    cached_data = cache_service.get(cache_key)
    if cached_data:
        print(f"DEBUG: Returning cached data for {'admin' if user.is_admin else 'user'} {user.id}: {len(cached_data)} orders")
        return jsonify(cached_data)
    
    print(f"DEBUG: Cache miss - loading fresh data for {'admin' if user.is_admin else 'user'} {user.id}")
    
    # Import Listing at the top level
    from models.listing import Listing
    
    # If not cached, build the data with server-side filtering
    print(f"DEBUG: User {user.id} is_admin = {user.is_admin}")
    
    if user.is_admin:
        # Admins see all orders
        print("DEBUG: Loading all orders for admin")
        orders = Order.query.order_by(Order.created_at.desc()).all()
        print(f"DEBUG: Admin {user.id} found {len(orders)} orders")
        for i, order in enumerate(orders[:3]):  # Show first 3 orders
            print(f"DEBUG: Order {i+1}: ID={order.id}, seller={order.seller_name}, status={order.status}")
    else:
        # Regular users see: their own orders + building phase orders + closed orders they participated in
        print("DEBUG: Loading filtered orders for regular user")
        orders = Order.query.filter(
            db.or_(
                Order.creator_id == user.id,
                Order.listings.any(Listing.user_id == user.id),
                Order.status == 'building',
                db.and_(Order.status == 'closed', Order.listings.any(Listing.user_id == user.id)),
                db.and_(Order.status == 'deleted', Order.listings.any(Listing.user_id == user.id)),
                db.and_(Order.status == 'deleted', Order.creator_id == user.id)
            )
        ).order_by(Order.created_at.desc()).all()
        print(f"DEBUG: User {user.id} found {len(orders)} orders")
        for i, order in enumerate(orders[:3]):  # Show first 3 orders
            print(f"DEBUG: Order {i+1}: ID={order.id}, seller={order.seller_name}, status={order.status}, creator={order.creator_id}")
    
    orders_data = []
    for order in orders:
        user_listings_count = Listing.query.filter_by(order_id=order.id, user_id=user.id).count()
        available_count = order.listings.filter_by(status='For Sale').count()

        # Use cached seller info (cached for 1 hour)
        seller_info_cache_key = f"seller_info_{order.seller_name}"
        seller_info = cache_service.get(seller_info_cache_key)
        if not seller_info:
            seller_info = discogs_service.fetch_seller_info(order.seller_name)
            cache_service.set(seller_info_cache_key, seller_info, expire_seconds=3600)
        
        # Use cached inventory count (cached for 1 hour)
        inventory_cache_key = f"seller_inventory_count_{order.seller_name}"
        seller_inventory_count = cache_service.get(inventory_cache_key)
        if seller_inventory_count is None:
            seller_inventory_count = discogs_service.fetch_seller_inventory_count(order.seller_name)
            cache_service.set(inventory_cache_key, seller_inventory_count, expire_seconds=3600)
        
        # Calculate wantlist matches for the current user only
        wantlist_matches = 0
        
        # Get current user's wantlist items
        user_wantlist_items = WantlistItem.query.filter_by(user_id=user.id).all()
        
        if user_wantlist_items:
            # Get seller's listings for this order
            seller_listings = order.listings.filter_by(status='For Sale').all()
            
            # Count matches between user's wantlist and seller's listings
            for wantlist_item in user_wantlist_items:
                for listing in seller_listings:
                    # Match by release ID
                    if str(wantlist_item.release_id) == str(listing.release_id):
                        wantlist_matches += 1
                        break  # Found a match, move to next wantlist item
        
        order_data = order.to_dict()
        order_data.update({
            'available_count': available_count,
            'user_listings_count': user_listings_count,
            'is_creator': order.creator_id == user.id,
            'is_participant': user_listings_count > 0,
            'seller_info': seller_info,
            'seller_inventory_count': seller_inventory_count,
            'user_wantlist_matches': wantlist_matches,
        })
        
        orders_data.append(order_data)
    
    # Cache the entire dashboard data for 1 hour
    cache_service.set(cache_key, orders_data, expire_seconds=3600)
    
    print(f"DEBUG: Returning {len(orders_data)} orders to {'admin' if user.is_admin else 'user'} {user.id}")
    if orders_data:
        print(f"DEBUG: First order data: {orders_data[0]}")
        # Show all order statuses
        statuses = [order.get('status') for order in orders_data]
        print(f"DEBUG: Order statuses: {statuses}")
    
    return jsonify(orders_data)

@orders_api.route('/orders/cache/clear', methods=['POST'])
def clear_dashboard_cache():
    """Clear dashboard cache for all users (admin only)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        # Clear all dashboard caches
        from services.cache_service import invalidate_cache_pattern
        invalidate_cache_pattern("dashboard_orders_*")
        invalidate_cache_pattern("seller_info_*")
        invalidate_cache_pattern("seller_inventory_count_*")
        
        return jsonify({'success': True, 'message': 'Dashboard cache cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@orders_api.route('/orders/cache/clear/user', methods=['POST'])
def clear_user_cache():
    """Clear dashboard cache for current user"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    
    try:
        # Clear cache for current user
        cache_service.delete(f"dashboard_orders_{user.id}_{user.is_admin}")
        
        return jsonify({'success': True, 'message': f'Cache cleared for user {user.id}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@orders_api.route('/jobs/trigger', methods=['POST'])
def trigger_manual_job():
    """Trigger a manual background job (admin only)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json()
    job_type = data.get('job_type', '')
    
    if not job_type:
        return jsonify({'error': 'job_type required'}), 400
    
    try:
        from services import background_job_service
        success = background_job_service.trigger_manual_refresh(job_type)
        
        if success:
            return jsonify({'success': True, 'message': f'Job {job_type} triggered successfully'})
        else:
            return jsonify({'error': f'Failed to trigger job {job_type}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        
        if 'paypal_link' in data:
            order.paypal_link = data['paypal_link'].strip() if data['paypal_link'] else None
        
        if 'user_location' in data:
            order.user_location = data['user_location'].strip() if data['user_location'] else None
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Paramètres mis à jour avec succès'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@orders_api.route('/orders/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    """Delete order - soft delete for regular users, hard delete for admin if already deleted"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    if order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Only creator can delete order'}), 403
    
    try:
        # Check if order is already deleted
        if order.status == 'deleted':
            # If already deleted and user is admin, permanently delete from database
            if current_user.is_admin:
                db.session.delete(order)
                db.session.commit()
                
                # Clear cache to reflect the permanent deletion
                from services.cache_service import invalidate_cache_pattern
                print(f"DEBUG: Permanently deleting order {order_id} from database")
                invalidate_cache_pattern("dashboard_orders_*")
                cache_service.delete(f"dashboard_orders_{current_user.id}_{current_user.is_admin}")
                print(f"DEBUG: Cleared cache for permanent deletion")
                
                return jsonify({'success': True, 'message': 'Commande définitivement supprimée'})
            else:
                return jsonify({'error': 'Commande déjà supprimée'}), 400
        else:
            # First deletion - set status to 'deleted' (soft delete)
            order.status = 'deleted'
            db.session.commit()
            
            # Clear cache to reflect the change
            from services.cache_service import invalidate_cache_pattern
            print(f"DEBUG: Soft deleting order {order_id}")
            invalidate_cache_pattern("dashboard_orders_*")
            cache_service.delete(f"dashboard_orders_{current_user.id}_{current_user.is_admin}")
            print(f"DEBUG: Cleared cache for soft deletion")
            
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

@orders_api.route('/orders/<int:order_id>/participant-summary', methods=['GET'])
def get_participant_summary(order_id):
    """Get participant summary for an order"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    # Check if user has access to this order
    user_listing_count = order.listings.filter_by(user_id=current_user.id).count()
    if user_listing_count == 0 and order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied to this order'}), 403
    
    try:
        # Get all participants summary
        participants_summary = order.get_all_participants_summary()
        
        # Convert to list format for frontend, sorted with creator first
        summary_list = []
        for participant_id, data in participants_summary.items():
            summary_list.append(data)
        
        # Sort with creator first, then by username
        summary_list.sort(key=lambda x: (not x['user']['is_creator'], x['user']['username']))
        
        return jsonify(summary_list)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500