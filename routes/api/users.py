from flask import Blueprint, request, jsonify
from models import db, User
from services import auth_service, discogs_service

users_api = Blueprint('users_api', __name__)

@users_api.route('/user/profile', methods=['GET'])
def get_user_profile():
    """Get current user profile"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    return jsonify(user.to_dict())

@users_api.route('/user/profile', methods=['PUT'])
def update_user_profile():
    """Update current user profile"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    data = request.get_json()
    
    try:
        # Update mutual order username if provided
        if 'mutual_order_username' in data:
            new_username = data['mutual_order_username'].strip()
            
            # Validate the new username
            available, message = auth_service.check_username_availability(new_username, user.id)
            if not available:
                return jsonify({'error': message}), 400
            
            user.mutual_order_username = new_username
            if not user.profile_completed:
                user.profile_completed = True
        
        # Update default location if provided
        if 'default_location' in data:
            user.default_location = data['default_location'].strip() if data['default_location'] else None
        
        # Update default PayPal link if provided
        if 'default_paypal_link' in data:
            paypal_link = data['default_paypal_link'].strip() if data['default_paypal_link'] else None
            # Basic validation for PayPal.me links
            if paypal_link and not paypal_link.startswith(('https://paypal.me/', 'https://www.paypal.me/')):
                return jsonify({'error': 'Le lien PayPal.me doit commencer par https://paypal.me/'}), 400
            user.default_paypal_link = paypal_link
        
        db.session.commit()
        return jsonify({
            'success': True,
            'user': user.to_dict(),
            'message': 'Profile updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@users_api.route('/user/wantlist', methods=['GET'])
def get_user_wantlist():
    """Get user's Discogs wantlist"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    
    try:
        wantlist = discogs_service.get_user_wantlist(
            user.id,
            user.discogs_username,
            user.discogs_access_token,
            user.discogs_access_secret
        )
        
        return jsonify({
            'wantlist': wantlist,
            'total_count': len(wantlist),
            'discogs_username': user.discogs_username
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@users_api.route('/check_username', methods=['POST'])
def check_username():
    """Check if username is available"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    username = data.get('username', '').strip()
    current_user = auth_service.get_current_user()
    
    available, message = auth_service.check_username_availability(username, current_user.id)
    
    return jsonify({
        'available': available,
        'message': message
    })

@users_api.route('/users/search', methods=['GET'])
def search_users():
    """Search users by username (for admin/debugging)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    current_user = auth_service.get_current_user()
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    query = request.args.get('q', '').strip()
    limit = min(request.args.get('limit', 10, type=int), 50)
    
    if len(query) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400
    
    # Search by mutual_order_username or discogs_username
    users = User.query.filter(
        db.or_(
            User.mutual_order_username.ilike(f'%{query}%'),
            User.discogs_username.ilike(f'%{query}%')
        )
    ).limit(limit).all()
    
    return jsonify({
        'users': [user.to_dict() for user in users],
        'query': query,
        'count': len(users)
    })

@users_api.route('/sellers/<seller_name>', methods=['GET'])
def get_seller_info(seller_name):
    """Get seller information from Discogs"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        seller_info = discogs_service.fetch_seller_info(seller_name)
        return jsonify(seller_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@users_api.route('/user/stats', methods=['GET'])
def get_user_stats():
    """Get current user statistics"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    
    # Get user statistics
    from models import Order, Listing
    
    stats = {
        'orders_created': Order.query.filter_by(creator_id=user.id).count(),
        'orders_participated': Order.query.join(Listing).filter(Listing.user_id == user.id).distinct().count(),
        'total_listings': Listing.query.filter_by(user_id=user.id).count(),
        'active_listings': Listing.query.filter_by(user_id=user.id, status='For Sale').count(),
        'total_spent': db.session.query(db.func.sum(Listing.price_value)).filter_by(user_id=user.id).scalar() or 0,
        'account_age_days': (db.func.julianday('now') - db.func.julianday(user.created_at)).label('age')
    }
    
    # Get recent activity
    recent_listings = Listing.query.filter_by(user_id=user.id).order_by(Listing.added_at.desc()).limit(5).all()
    recent_orders = Order.query.filter_by(creator_id=user.id).order_by(Order.created_at.desc()).limit(5).all()
    
    return jsonify({
        'stats': stats,
        'recent_listings': [listing.to_dict() for listing in recent_listings],
        'recent_orders': [order.to_dict() for order in recent_orders]
    })