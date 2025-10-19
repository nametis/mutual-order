from flask import Blueprint, request, jsonify
from models import db, Order, Listing
from services import discogs_service, auth_service

listings_api = Blueprint('listings_api', __name__)

@listings_api.route('/orders/<int:order_id>/listings', methods=['POST'])
def add_listing(order_id):
    """Add a new listing to an order"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    listing_url = data.get('listing_url', '').strip()
    
    if not listing_url:
        return jsonify({'error': 'URL required'}), 400
    
    order = Order.query.get_or_404(order_id)
    listing_id = discogs_service.extract_listing_id(listing_url)
    
    if not listing_id:
        return jsonify({'error': 'Invalid Discogs URL'}), 400
    
    # Check if listing already exists in this order
    existing = Listing.query.filter_by(discogs_id=listing_id, order_id=order_id).first()
    if existing:
        return jsonify({'error': 'Listing already exists in this order'}), 400
    
    current_user = auth_service.get_current_user()
    
    try:
        listing_data = discogs_service.fetch_listing_data(listing_id)
        
        # Verify seller matches order
        if listing_data['seller_name'] != order.seller_name:
            return jsonify({
                'error': f'Wrong seller: expected {order.seller_name}, got {listing_data["seller_name"]}'
            }), 400
        
        # Create new listing
        listing = Listing(
            discogs_id=listing_data['id'],
            release_id=listing_data.get('release_id'),
            title=listing_data['title'],
            price_value=listing_data['price_value'],
            currency=listing_data['currency'],
            media_condition=listing_data['media_condition'],
            sleeve_condition=listing_data['sleeve_condition'],
            image_url=listing_data['image_url'],
            listing_url=listing_url,
            status=listing_data['status'],
            user_id=current_user.id,
            order_id=order_id
        )
        
        db.session.add(listing)
        db.session.commit()
        
        # Clear dashboard cache since new listing was added
        try:
            from services import cache_service
            from services.cache_service import invalidate_cache_pattern
            invalidate_cache_pattern("dashboard_orders_*")
            current_app.logger.info("Dashboard cache cleared after listing addition")
        except Exception as e:
            current_app.logger.error(f"Error clearing cache: {e}")
        
        return jsonify(listing.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@listings_api.route('/listings/<int:listing_id>', methods=['DELETE'])
def delete_listing(listing_id):
    """Delete a listing"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    listing = Listing.query.get_or_404(listing_id)
    current_user = auth_service.get_current_user()
    
    # Check if user owns this listing or is admin
    if listing.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Not authorized'}), 403
    
    try:
        db.session.delete(listing)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@listings_api.route('/listings/<int:listing_id>', methods=['PUT'])
def update_listing(listing_id):
    """Update listing details"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    listing = Listing.query.get_or_404(listing_id)
    current_user = auth_service.get_current_user()
    
    # Check if user owns this listing or is admin
    if listing.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Not authorized'}), 403
    
    data = request.get_json()
    
    try:
        # Update allowed fields
        if 'title' in data:
            listing.title = data['title']
        if 'price_value' in data:
            listing.price_value = float(data['price_value'])
        if 'currency' in data:
            listing.currency = data['currency']
        if 'media_condition' in data:
            listing.media_condition = data['media_condition']
        if 'sleeve_condition' in data:
            listing.sleeve_condition = data['sleeve_condition']
        if 'status' in data:
            listing.status = data['status']
        
        db.session.commit()
        return jsonify(listing.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@listings_api.route('/listings/<int:listing_id>/refresh', methods=['POST'])
def refresh_listing(listing_id):
    """Refresh listing data from Discogs"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    listing = Listing.query.get_or_404(listing_id)
    current_user = auth_service.get_current_user()
    
    # Check if user owns this listing or is admin
    if listing.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Not authorized'}), 403
    
    try:
        # Fetch fresh data from Discogs
        listing_data = discogs_service.fetch_listing_data(listing.discogs_id)
        
        # Update listing with fresh data
        listing.update_from_discogs_data(listing_data)
        
        db.session.commit()
        return jsonify({
            'success': True,
            'listing': listing.to_dict(),
            'message': 'Listing refreshed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to refresh listing: {str(e)}'}), 500