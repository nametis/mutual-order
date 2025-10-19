from flask import Blueprint, request, jsonify
from models import db, User, FavoriteSeller, Friend, FriendRequest
from services import auth_service, discogs_service
import re

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

# Favorite Sellers API
@users_api.route('/user/favorite_sellers', methods=['GET'])
def get_favorite_sellers():
    """Get user's favorite sellers"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    sellers = FavoriteSeller.query.filter_by(user_id=user.id).all()
    
    return jsonify({
        'sellers': [seller.to_dict() for seller in sellers]
    })

@users_api.route('/user/favorite_sellers', methods=['POST'])
def add_favorite_seller():
    """Add a favorite seller"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    data = request.get_json()
    
    if 'url' in data:
        # Extract seller name from Discogs URL or use as plain text
        url = data['url'].strip()
        seller_name = extract_seller_from_url(url)
        if not seller_name:
            # If it's not a URL, treat it as a plain seller name
            seller_name = url
    elif 'seller' in data:
        seller_name = data['seller'].strip()
    else:
        return jsonify({'error': 'URL ou nom de vendeur requis'}), 400
    
    # Check if already exists
    existing = FavoriteSeller.query.filter_by(user_id=user.id, seller_name=seller_name).first()
    if existing:
        return jsonify({'error': 'Ce vendeur est déjà dans vos favoris'}), 400
    
    # Create new favorite seller
    favorite_seller = FavoriteSeller(
        user_id=user.id,
        seller_name=seller_name,
        shop_url=f"https://www.discogs.com/seller/{seller_name}" if 'url' not in data else data.get('url', '')
    )
    
    db.session.add(favorite_seller)
    db.session.commit()
    
    return jsonify({
        'message': 'Vendeur ajouté aux favoris',
        'seller': favorite_seller.to_dict()
    })

@users_api.route('/user/favorite_sellers/<seller_name>', methods=['DELETE'])
def remove_favorite_seller(seller_name):
    """Remove a favorite seller"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    favorite_seller = FavoriteSeller.query.filter_by(user_id=user.id, seller_name=seller_name).first()
    
    if not favorite_seller:
        return jsonify({'error': 'Vendeur non trouvé dans vos favoris'}), 404
    
    db.session.delete(favorite_seller)
    db.session.commit()
    
    return jsonify({'message': 'Vendeur retiré des favoris'})

# Friends API
@users_api.route('/user/friends', methods=['GET'])
def get_friends():
    """Get user's friends"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    friends = Friend.query.filter_by(user_id=user.id).all()
    
    return jsonify({
        'friends': [friend.to_dict() for friend in friends]
    })

@users_api.route('/user/friends', methods=['POST'])
def add_friend():
    """Send a friend request"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    data = request.get_json()
    
    if 'url' in data:
        # Extract username from profile URL
        url = data['url'].strip()
        username = extract_username_from_url(url)
        if not username:
            return jsonify({'error': 'URL invalide. Utilisez une URL de profil ou un nom d\'utilisateur.'}), 400
    elif 'username' in data:
        username = data['username'].strip()
        # Remove @ if present
        if username.startswith('@'):
            username = username[1:]
    else:
        return jsonify({'error': 'URL ou nom d\'utilisateur requis'}), 400
    
    # Find the friend user - try mutual_order_username first, then discogs_username
    friend_user = User.query.filter_by(mutual_order_username=username).first()
    if not friend_user:
        friend_user = User.query.filter_by(discogs_username=username).first()
    if not friend_user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404
    
    if friend_user.id == user.id:
        return jsonify({'error': 'Vous ne pouvez pas vous ajouter vous-même'}), 400
    
    # Check if already friends
    existing_friendship = Friend.query.filter_by(user_id=user.id, friend_user_id=friend_user.id).first()
    if existing_friendship:
        print(f"DEBUG: User {user.id} already has friendship with {friend_user.id}")
        return jsonify({'error': 'Cet utilisateur est déjà dans vos amis'}), 400
    
    # Clean up any old requests (accepted, declined, or pending) between these users
    # This allows re-adding friends after deletion
    old_requests = FriendRequest.query.filter(
        ((FriendRequest.requester_id == user.id) & (FriendRequest.requested_id == friend_user.id)) |
        ((FriendRequest.requester_id == friend_user.id) & (FriendRequest.requested_id == user.id))
    ).all()
    
    for old_request in old_requests:
        print(f"DEBUG: Cleaning up old request {old_request.id} (status: {old_request.status})")
        db.session.delete(old_request)
    
    # Commit the cleanup
    if old_requests:
        db.session.commit()
        print(f"DEBUG: Cleaned up {len(old_requests)} old requests")
    
    # Create friend request
    friend_request = FriendRequest(
        requester_id=user.id,
        requested_id=friend_user.id
    )
    
    db.session.add(friend_request)
    db.session.commit()
    
    return jsonify({
        'message': 'Demande d\'amitié envoyée',
        'friend_request': friend_request.to_dict()
    })

@users_api.route('/user/friends/<username>', methods=['DELETE'])
def remove_friend(username):
    """Remove a friend"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    
    # Remove @ if present
    if username.startswith('@'):
        username = username[1:]
    
    # Find the friend user
    friend_user = User.query.filter_by(mutual_order_username=username).first()
    if not friend_user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404
    
    # Remove both friendship records (bidirectional)
    friend1 = Friend.query.filter_by(user_id=user.id, friend_user_id=friend_user.id).first()
    friend2 = Friend.query.filter_by(user_id=friend_user.id, friend_user_id=user.id).first()
    
    if not friend1 and not friend2:
        return jsonify({'error': 'Cet utilisateur n\'est pas dans vos amis'}), 404
    
    if friend1:
        db.session.delete(friend1)
    if friend2:
        db.session.delete(friend2)
    
    # Also clean up any old friend requests between these users
    old_requests = FriendRequest.query.filter(
        ((FriendRequest.requester_id == user.id) & (FriendRequest.requested_id == friend_user.id)) |
        ((FriendRequest.requester_id == friend_user.id) & (FriendRequest.requested_id == user.id))
    ).all()
    
    for old_request in old_requests:
        print(f"DEBUG: Cleaning up old request {old_request.id} (status: {old_request.status}) during friend removal")
        db.session.delete(old_request)
    
    db.session.commit()
    
    return jsonify({'message': 'Ami retiré'})

# Public profile API endpoints
@users_api.route('/user/favorite_sellers/<username>', methods=['GET'])
def get_public_favorite_sellers(username):
    """Get favorite sellers for a public profile"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Find the user
    user = User.query.filter_by(mutual_order_username=username).first()
    if not user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404
    
    sellers = FavoriteSeller.query.filter_by(user_id=user.id).all()
    
    return jsonify({
        'sellers': [seller.to_dict() for seller in sellers]
    })

@users_api.route('/user/friends/<username>', methods=['GET'])
def get_public_friends(username):
    """Get friends for a public profile"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Find the user
    user = User.query.filter_by(mutual_order_username=username).first()
    if not user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404
    
    friends = Friend.query.filter_by(user_id=user.id).all()
    
    return jsonify({
        'friends': [friend.to_dict() for friend in friends]
    })

@users_api.route('/user/friends/check/<username>', methods=['GET'])
def check_friendship_status(username):
    """Check if current user is friends with the given username"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    current_user = auth_service.get_current_user()
    
    # Find the target user - try mutual_order_username first, then discogs_username
    target_user = User.query.filter_by(mutual_order_username=username).first()
    if not target_user:
        target_user = User.query.filter_by(discogs_username=username).first()
    if not target_user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404
    
    # Check if they are friends
    friendship = Friend.query.filter_by(
        user_id=current_user.id, 
        friend_user_id=target_user.id
    ).first()
    
    # Check if there's a pending request from current user to target user
    pending_request = FriendRequest.query.filter_by(
        requester_id=current_user.id,
        requested_id=target_user.id,
        status='pending'
    ).first()
    
    return jsonify({
        'is_friend': friendship is not None,
        'has_pending_request': pending_request is not None
    })

# Friend Request API endpoints
@users_api.route('/user/friend_requests', methods=['GET'])
def get_friend_requests():
    """Get pending friend requests received by current user"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    requests = FriendRequest.query.filter_by(requested_id=user.id, status='pending').all()
    
    return jsonify({
        'friend_requests': [req.to_dict() for req in requests]
    })

@users_api.route('/user/friend_requests/<int:request_id>/accept', methods=['POST'])
def accept_friend_request(request_id):
    """Accept a friend request"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    friend_request = FriendRequest.query.filter_by(
        id=request_id, 
        requested_id=user.id, 
        status='pending'
    ).first()
    
    if not friend_request:
        return jsonify({'error': 'Demande d\'amitié non trouvée'}), 404
    
    # Create bidirectional friendship
    friend1 = Friend(
        user_id=friend_request.requester_id,
        friend_user_id=friend_request.requested_id
    )
    friend2 = Friend(
        user_id=friend_request.requested_id,
        friend_user_id=friend_request.requester_id
    )
    
    # Update request status
    friend_request.status = 'accepted'
    friend_request.responded_at = db.func.now()
    
    db.session.add(friend1)
    db.session.add(friend2)
    db.session.commit()
    
    return jsonify({
        'message': 'Demande d\'amitié acceptée',
        'friend': friend1.to_dict()
    })

@users_api.route('/user/friend_requests/<int:request_id>/decline', methods=['POST'])
def decline_friend_request(request_id):
    """Decline a friend request"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    friend_request = FriendRequest.query.filter_by(
        id=request_id, 
        requested_id=user.id, 
        status='pending'
    ).first()
    
    if not friend_request:
        return jsonify({'error': 'Demande d\'amitié non trouvée'}), 404
    
    # Update request status
    friend_request.status = 'declined'
    friend_request.responded_at = db.func.now()
    
    db.session.commit()
    
    return jsonify({'message': 'Demande d\'amitié refusée'})

def extract_seller_from_url(url):
    """Extract seller name from various Discogs URL formats"""
    patterns = [
        r'discogs\.com/seller/([^/?]+)',
        r'discogs\.com/user/([^/?]+)',
        r'discogs\.com/sell/item/\d+.*seller=([^&]+)',
        r'discogs\.com/fr/seller/([^/?]+)',  # French Discogs URLs
        r'discogs\.com/fr/user/([^/?]+)',   # French Discogs URLs
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def extract_username_from_url(url):
    """Extract username from profile URL"""
    patterns = [
        r'/(?:@|u/)([^/?]+)',
        r'/([^/?]+)$',  # fallback for simple usernames
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None