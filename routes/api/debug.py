"""
Debug API endpoints for testing features
"""
from flask import Blueprint, jsonify, request, current_app
from services import auth_service, wantlist_matching_service, cache_service
from datetime import datetime, timezone
import json
import threading
import time

debug_api = Blueprint('debug_api', __name__)

# Request deduplication - prevent multiple simultaneous requests for the same data
_active_requests = {}
_request_locks = {}

@debug_api.route('/debug/wantlist-matches', methods=['GET'])
def get_wantlist_matches():
    """Get wantlist matches for the current user with request deduplication"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    
    # Check for bypass_cache parameter
    bypass_cache = request.args.get('bypass_cache', 'false').lower() == 'true'
    
    # Check for cached result first (unless bypassing cache)
    if not bypass_cache:
        cache_key = f"wantlist_matches_result_{user.id}_false"
        cached_result = cache_service.get(cache_key)
        if cached_result:
            current_app.logger.info(f"✅ API CACHE HIT for wantlist matches (user {user.id})")
            return jsonify(json.loads(cached_result))
    
    # Create a unique request key for deduplication
    request_key = f"wantlist_matches_{user.id}_{bypass_cache}"
    
    # Check if there's already an active request for this user
    if request_key in _active_requests:
        current_app.logger.info(f"🔄 Request deduplication: Waiting for existing request for user {user.id}")
        # Wait for the existing request to complete
        while request_key in _active_requests:
            time.sleep(0.1)
        
        # Try to get cached result after waiting
        cache_key = f"wantlist_matches_result_{user.id}_{bypass_cache}"
        cached_result = cache_service.get(cache_key)
        if cached_result:
            current_app.logger.info(f"✅ Returning cached result after deduplication for user {user.id}")
            return jsonify(json.loads(cached_result))
    
    # Mark this request as active
    _active_requests[request_key] = True
    current_app.logger.info(f"🚀 Processing wantlist matches for user {user.id} (bypass_cache={bypass_cache})")
    
    try:
        results = wantlist_matching_service.get_wantlist_matches_for_user(user.id, bypass_cache)
        
        # Cache the result for 5 minutes to handle deduplication
        cache_key = f"wantlist_matches_result_{user.id}_{bypass_cache}"
        cache_service.set(cache_key, json.dumps(results), expire_seconds=300)
        
        # If bypass_cache was used, also clear the full cache to force refresh next time
        if bypass_cache:
            full_cache_key = f"wantlist_matches_full_{user.id}"
            cache_service.delete(full_cache_key)
            current_app.logger.info(f"🗑️ Cleared full cache for user {user.id} due to bypass")
        
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Error getting wantlist matches for user {user.id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Remove from active requests
        _active_requests.pop(request_key, None)
        current_app.logger.info(f"✅ Completed wantlist matches for user {user.id}")

@debug_api.route('/debug/clear-wantlist-cache', methods=['POST'])
def clear_wantlist_cache():
    """Clear wantlist-specific cache entries for current user"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        # Clear wantlist-specific cache entries
        cache_keys_to_clear = [
            f"wantlist_matches_full_{user.id}",
            f"wantlist_matches_result_{user.id}_false",
            f"wantlist_matches_result_{user.id}_true",
            f"cache_status_full_{user.id}",
            f"cache_status_result_{user.id}",
            "registered_sellers_list"
        ]
        
        cleared_count = 0
        for cache_key in cache_keys_to_clear:
            if cache_service.delete(cache_key):
                cleared_count += 1
        
        return jsonify({
            'message': f'Cleared {cleared_count} wantlist cache entries for user {user.id}',
            'cleared_keys': cache_keys_to_clear,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/refresh-seller', methods=['POST'])
def refresh_seller_inventory():
    """Force refresh a specific seller's inventory"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    data = request.get_json()
    
    if not data or 'seller_name' not in data:
        return jsonify({'error': 'seller_name required'}), 400

    seller_name = data['seller_name']
    
    try:
        current_app.logger.info(f"🚀 FRONTEND REFRESH - {seller_name} (PURE INVENTORY ONLY)")
        
        # Clear cache first
        cache_key = wantlist_matching_service._get_seller_inventory_cache_key(seller_name, user.id)
        metadata_key = wantlist_matching_service._get_seller_inventory_metadata_key(seller_name)
        cache_service.delete(cache_key)
        cache_service.delete(metadata_key)
        
        # Fetch fresh inventory directly (NO wantlist processing)
        inventory = wantlist_matching_service.discogs_service.fetch_seller_inventory(
            seller_name, 
            user.discogs_access_token, 
            user.discogs_access_secret
        )
        
        if inventory:
            # Cache the inventory
            wantlist_matching_service._cache_seller_inventory(seller_name, user.id, inventory)
            current_app.logger.info(f"✅ FRONTEND REFRESH COMPLETED - {seller_name}: {len(inventory)} items cached")
            
            return jsonify({
                'success': True,
                'seller_name': seller_name,
                'inventory_count': len(inventory),
                'message': f'Pure inventory refresh for {seller_name} - NO wantlist matching'
            })
        else:
            current_app.logger.warning(f"❌ FRONTEND REFRESH FAILED - {seller_name}: No inventory fetched")
            return jsonify({'error': 'Failed to refresh inventory'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error in frontend refresh for {seller_name}: {e}")
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/clear-cache', methods=['POST'])
def clear_cache():
    """Clear all seller inventory cache"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        from models import Order
        open_orders = Order.query.filter(
            Order.status.in_(['building', 'validation'])
        ).all()
        
        cleared_count = 0
        for order in open_orders:
            seller_name = order.seller_name
            cache_key = f"seller_inventory:{seller_name}:{user.id}"
            metadata_key = f"seller_metadata:{seller_name}"
            
            if cache_service.delete(cache_key) and cache_service.delete(metadata_key):
                cleared_count += 1
        
        return jsonify({
            'success': True,
            'cleared_sellers': cleared_count
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/job-status', methods=['GET'])
def get_job_status():
    """Get background job status"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        from services import background_job_service
        status = background_job_service.get_job_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/trigger-job', methods=['POST'])
def trigger_job():
    """Manually trigger a background job"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    if not data or 'job_type' not in data:
        return jsonify({'error': 'job_type required'}), 400

    job_type = data['job_type']
    valid_jobs = ['seller_inventories', 'user_wantlists', 'active_sellers', 'cache_cleanup']
    
    if job_type not in valid_jobs:
        return jsonify({'error': f'Invalid job_type. Must be one of: {valid_jobs}'}), 400

    try:
        from services import background_job_service
        success = background_job_service.trigger_manual_refresh(job_type)
        
        if success:
            return jsonify({'success': True, 'message': f'Job {job_type} triggered successfully'})
        else:
            return jsonify({'error': f'Failed to trigger job {job_type}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/refresh-factoryudine-complete', methods=['POST'])
def refresh_factoryudine_complete():
    """Special complete refresh for FactoryUdine to get all items using two-direction approach"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        # Get cached inventory for FactoryUdine
        cached_inventory, metadata = wantlist_matching_service._get_cached_seller_inventory(
            'FactoryUdine', user.id
        )
        
        if not cached_inventory:
            return jsonify({'error': 'No cached inventory found for FactoryUdine. Please refresh normally first.'}), 400
        
        # Use complete fetch method (now returns all items via pagination)
        complete_inventory, api_head_20 = wantlist_matching_service.discogs_service.fetch_seller_inventory_complete(
            'FactoryUdine',
            user.discogs_access_token,
            user.discogs_access_secret,
            cached_inventory
        )
        
        # Update cache with complete inventory
        if complete_inventory:
            # Find most recent listing date
            most_recent_date = None
            for item in complete_inventory:
                if 'listed_date' in item and item['listed_date']:
                    if not most_recent_date or item['listed_date'] > most_recent_date:
                        most_recent_date = item['listed_date']
            
            # Update metadata
            metadata.update({
                'count': len(complete_inventory),
                'cached_at': datetime.now(timezone.utc).isoformat(),
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'is_large_seller': True,
                'listing_ids': [item['id'] for item in complete_inventory],
                'most_recent_listing_date': most_recent_date,
                'api_head_20': api_head_20  # Store first 20 from API call for debug
            })
            
            # Cache the complete results
            wantlist_matching_service._cache_seller_inventory('FactoryUdine', user.id, complete_inventory, metadata)
            
            return jsonify({
                'success': True,
                'seller_name': 'FactoryUdine',
                'previous_count': len(cached_inventory) if cached_inventory else 0,
                'new_count': len(complete_inventory),
                'added_items': len(complete_inventory) - (len(cached_inventory) if cached_inventory else 0),
                'message': f'Complete inventory updated: {len(complete_inventory)} items fetched via pagination'
            })
        else:
            return jsonify({
                'success': True,
                'message': 'No items found',
                'count': 0
            })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/factoryudine-debug', methods=['GET'])
def get_factoryudine_debug():
    """Get debug data for FactoryUdine showing most recent and oldest listings"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        # Get cached inventory for FactoryUdine
        cached_inventory, metadata = wantlist_matching_service._get_cached_seller_inventory(
            'FactoryUdine', user.id
        )
        
        if not cached_inventory:
            return jsonify({'error': 'No cached inventory found for FactoryUdine'}), 400
        
        # Sort by title to get reverse alphabetical order (descending) 
        sorted_inventory_desc = sorted(cached_inventory, 
                                     key=lambda x: x.get('title', '').lower(), 
                                     reverse=True)
        
        # Get tail 20 of cache (oldest cached items when sorted desc)
        tail_cache = sorted_inventory_desc[-20:]
        
        # Make a direct API call to get first page data
        from services.discogs_service import discogs_service
        oauth = discogs_service.get_oauth_session(user.discogs_access_token, user.discogs_access_secret)
        
        response = oauth.get(
            f'https://api.discogs.com/users/FactoryUdine/inventory',
            params={
                'page': 1,
                'per_page': 20  # Get first 20 items
            }
        )
        
        if response.status_code != 200:
            return jsonify({'error': f'API call failed: {response.status_code}'}), 500
        
        data = response.json()
        raw_api_listings = data.get('listings', [])
        pagination = data.get('pagination', {})
        
        # Process raw API data for display
        api_head_20 = []
        for listing in raw_api_listings:
            release = listing.get('release', {})
            api_head_20.append({
                'id': str(listing.get('id')),
                'release_id': str(release.get('id')) if release.get('id') else None,
                'title': release.get('title', 'Unknown'),
                'price_value': float(listing.get('price', {}).get('value', 0)),
                'currency': listing.get('price', {}).get('currency', 'USD'),
                'media_condition': listing.get('condition', 'Unknown'),
                'sleeve_condition': listing.get('sleeve_condition', 'Unknown'),
                'listing_url': f"https://www.discogs.com/sell/item/{listing.get('id')}",
                'status': listing.get('status', 'For Sale'),
                'listed_date': listing.get('listed', '')
            })
        
        return jsonify({
            'tail_cache': tail_cache,
            'api_head_20': api_head_20,
            'total_count': len(cached_inventory),
            'raw_api_count': len(raw_api_listings),
            'pagination': {
                'total_items': pagination.get('items', 0),
                'total_pages': pagination.get('pages', 0),
                'current_page': pagination.get('page', 1)
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/clear-factoryudine-cache', methods=['POST'])
def clear_factoryudine_cache():
    """Clear FactoryUdine cache to force refresh with new sorting"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        # Clear FactoryUdine cache for this user
        cache_key = f"seller_inventory:FactoryUdine:{user.id}"
        metadata_key = f"seller_metadata:FactoryUdine:{user.id}"
        
        cache_service.delete(cache_key)
        cache_service.delete(metadata_key)
        
        return jsonify({
            'success': True,
            'message': 'FactoryUdine cache cleared successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/refresh-all-sellers', methods=['POST'])
def refresh_all_sellers():
    """Refresh all registered sellers and show which are classified as Large Sellers"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        # Get all registered sellers
        sellers = wantlist_matching_service.get_all_registered_sellers()
        
        if not sellers:
            return jsonify({'message': 'No registered sellers found'})
        
        # Refresh all sellers
        wantlist_matching_service.refresh_all_registered_sellers(
            user.id,
            user.discogs_access_token,
            user.discogs_access_secret
        )
        
        return jsonify({
            'message': f'Refresh initiated for {len(sellers)} registered sellers',
            'sellers': sellers
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/large-sellers', methods=['GET'])
def get_large_sellers():
    """Get list of sellers classified as Large Sellers (API limit exceeded)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        sellers = wantlist_matching_service.get_all_registered_sellers()
        large_sellers = []
        
        for seller_name in sellers:
            cached_inventory, metadata = wantlist_matching_service._get_cached_seller_inventory(
                seller_name, user.id
            )
            
            if metadata and metadata.get('is_large_seller', False):
                large_sellers.append({
                    'seller_name': seller_name,
                    'cached_items': len(cached_inventory) if cached_inventory else 0,
                    'last_updated': metadata.get('last_updated')
                })
        
        return jsonify({
            'large_sellers': large_sellers,
            'total_large_sellers': len(large_sellers)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/seller-status/<seller_name>', methods=['GET'])
def get_seller_status(seller_name):
    """Get detailed status for a specific seller"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        # Check if seller is in registered sellers
        all_sellers = wantlist_matching_service.get_all_registered_sellers()
        is_registered = seller_name in all_sellers
        
        # Get cached inventory and metadata
        cached_inventory, metadata = wantlist_matching_service._get_cached_seller_inventory(
            seller_name, user.id
        )
        
        # Check if seller is too large for API
        is_large_seller = False
        total_pages = 0
        total_items = 0
        
        try:
            # Try to get pagination info
            oauth = wantlist_matching_service.discogs_service.get_oauth_session(
                user.discogs_access_token, user.discogs_access_secret
            )
            response = oauth.get(
                f'https://api.discogs.com/users/{seller_name}/inventory',
                params={'page': 1, 'per_page': 100}
            )
            
            if response.status_code == 200:
                data = response.json()
                pagination = data.get('pagination', {})
                total_pages = pagination.get('pages', 0)
                total_items = pagination.get('items', 0)
                is_large_seller = total_pages > 100
            else:
                total_pages = f"Error: {response.status_code}"
                total_items = f"Error: {response.status_code}"
                
        except Exception as e:
            total_pages = f"Error: {str(e)}"
            total_items = f"Error: {str(e)}"
        
        return jsonify({
            'seller_name': seller_name,
            'is_registered': is_registered,
            'cached_inventory_count': len(cached_inventory) if cached_inventory else 0,
            'metadata': metadata,
            'is_large_seller': is_large_seller,
            'total_pages': total_pages,
            'total_items': total_items,
            'all_registered_sellers': all_sellers
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/wantlist-matches-detailed', methods=['GET'])
def get_wantlist_matches_detailed():
    """Get detailed wantlist matches showing which sellers are processed"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        # Get wantlist matches
        matches_data = wantlist_matching_service.get_wantlist_matches_for_user(user.id)
        
        # Get all registered sellers
        all_sellers = wantlist_matching_service.get_all_registered_sellers()
        
        # Get seller status for each registered seller
        seller_statuses = []
        for seller_name in all_sellers:
            cached_inventory, metadata = wantlist_matching_service._get_cached_seller_inventory(
                seller_name, user.id
            )
            
            seller_statuses.append({
                'seller_name': seller_name,
                'has_cached_inventory': cached_inventory is not None,
                'cached_items_count': len(cached_inventory) if cached_inventory else 0,
                'is_large_seller': metadata.get('is_large_seller', False) if metadata else False,
                'last_updated': metadata.get('last_updated') if metadata else None
            })
        
        return jsonify({
            'wantlist_matches': matches_data,
            'registered_sellers': all_sellers,
            'seller_statuses': seller_statuses,
            'total_registered_sellers': len(all_sellers)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/orders-sellers', methods=['GET'])
def get_orders_sellers():
    """Get all seller names from orders to debug registration issues"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        from models.order import Order
        from models.favorite_seller import FavoriteSeller
        from models import db
        
        # Get all unique seller names from orders
        order_sellers = db.session.query(Order.seller_name).distinct().all()
        order_seller_names = [seller[0] for seller in order_sellers if seller[0]]
        
        # Get all unique seller names from favorite sellers
        favorite_sellers = db.session.query(FavoriteSeller.seller_name).distinct().all()
        favorite_seller_names = [seller[0] for seller in favorite_sellers if seller[0]]
        
        # Get all registered sellers (combined)
        all_registered = wantlist_matching_service.get_all_registered_sellers()
        
        return jsonify({
            'order_sellers': order_seller_names,
            'favorite_sellers': favorite_seller_names,
            'all_registered_sellers': all_registered,
            'total_order_sellers': len(order_seller_names),
            'total_favorite_sellers': len(favorite_sellers),
            'total_registered': len(all_registered)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/refresh-seller/<seller_name>', methods=['POST'])
def refresh_specific_seller(seller_name):
    """Manually refresh a specific seller's inventory (single seller only, no wantlist matching)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        current_app.logger.info(f"🔧 SINGLE SELLER REFRESH ONLY - {seller_name}")
        
        # Force refresh the seller's inventory
        inventory, metadata = wantlist_matching_service.force_refresh_seller_inventory(
            seller_name,
            user.id,
            user.discogs_access_token,
            user.discogs_access_secret
        )
        
        current_app.logger.info(f"✅ SINGLE SELLER REFRESH COMPLETED - {seller_name}: {len(inventory) if inventory else 0} items")
        
        return jsonify({
            'seller_name': seller_name,
            'inventory_count': len(inventory) if inventory else 0,
            'metadata': metadata,
            'success': inventory is not None,
            'message': f'Refreshed {seller_name} only - NO wantlist matching triggered'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error refreshing single seller {seller_name}: {e}")
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/refresh-seller-only/<seller_name>', methods=['POST'])
def refresh_seller_only(seller_name):
    """Refresh ONLY the seller inventory without any wantlist processing"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        current_app.logger.info(f"🚀 PURE INVENTORY REFRESH - {seller_name} (NO wantlist matching)")
        
        # Clear cache first
        cache_key = wantlist_matching_service._get_seller_inventory_cache_key(seller_name, user.id)
        metadata_key = wantlist_matching_service._get_seller_inventory_metadata_key(seller_name)
        cache_service.delete(cache_key)
        cache_service.delete(metadata_key)
        
        # Fetch fresh inventory directly
        inventory = wantlist_matching_service.discogs_service.fetch_seller_inventory(
            seller_name, 
            user.discogs_access_token, 
            user.discogs_access_secret
        )
        
        if inventory:
            # Cache the inventory
            wantlist_matching_service._cache_seller_inventory(seller_name, user.id, inventory)
            current_app.logger.info(f"✅ PURE REFRESH COMPLETED - {seller_name}: {len(inventory)} items cached")
        else:
            current_app.logger.warning(f"❌ PURE REFRESH FAILED - {seller_name}: No inventory fetched")
        
        return jsonify({
            'seller_name': seller_name,
            'inventory_count': len(inventory) if inventory else 0,
            'success': inventory is not None,
            'message': f'Pure inventory refresh for {seller_name} - NO wantlist processing'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in pure refresh for {seller_name}: {e}")
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/my-favorite-sellers', methods=['GET'])
def get_my_favorite_sellers():
    """Get favorite sellers for the current user"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        from models.favorite_seller import FavoriteSeller
        
        # Get favorite sellers for current user
        my_favorite_sellers = FavoriteSeller.query.filter_by(user_id=user.id).all()
        favorite_seller_data = [seller.to_dict() for seller in my_favorite_sellers]
        
        # Get all favorite sellers (for comparison)
        all_favorite_sellers = FavoriteSeller.query.distinct(FavoriteSeller.seller_name).all()
        all_favorite_seller_names = [seller.seller_name for seller in all_favorite_sellers]
        
        return jsonify({
            'my_favorite_sellers': favorite_seller_data,
            'my_favorite_seller_names': [seller['seller_name'] for seller in favorite_seller_data],
            'all_favorite_sellers': all_favorite_seller_names,
            'user_id': user.id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/cache-status', methods=['GET'])
def get_cache_status():
    """Get cache status for all registered sellers with request deduplication"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    # Create a unique request key for deduplication
    request_key = f"cache_status_{user.id}"
    
    # Check if there's already an active request for this user
    if request_key in _active_requests:
        current_app.logger.info(f"🔄 Request deduplication: Waiting for existing cache status request for user {user.id}")
        # Wait for the existing request to complete
        while request_key in _active_requests:
            time.sleep(0.1)
        
        # Try to get cached result
        cache_key = f"cache_status_result_{user.id}"
        cached_result = cache_service.get(cache_key)
        if cached_result:
            current_app.logger.info(f"✅ Returning cached cache status for user {user.id}")
            return jsonify(json.loads(cached_result))
    
    # Mark this request as active
    _active_requests[request_key] = True
    current_app.logger.info(f"🚀 Processing cache status for user {user.id}")
    
    try:
        # Check if we have a cached cache status result first
        cache_status_key = f"cache_status_full_{user.id}"
        cached_cache_status = cache_service.get(cache_status_key)
        if cached_cache_status:
            current_app.logger.info(f"✅ CACHE HIT for cache status (user {user.id})")
            return jsonify(json.loads(cached_cache_status))
        
        # Get all registered sellers
        registered_sellers = wantlist_matching_service.get_all_registered_sellers()
        
        cache_status = []
        
        for seller_name in registered_sellers:
            # Get cached inventory and metadata
            cached_inventory, metadata = wantlist_matching_service._get_cached_seller_inventory(
                seller_name, user.id
            )
            
            # Check if seller is too large for API
            is_large_seller = False
            total_pages = 0
            total_items = 0
            
            try:
                oauth = wantlist_matching_service.discogs_service.get_oauth_session(
                    user.discogs_access_token, user.discogs_access_secret
                )
                response = oauth.get(
                    f'https://api.discogs.com/users/{seller_name}/inventory',
                    params={'page': 1, 'per_page': 100}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    pagination = data.get('pagination', {})
                    total_pages = pagination.get('pages', 0)
                    total_items = pagination.get('items', 0)
                    is_large_seller = total_pages > 100
                else:
                    total_pages = f"Error: {response.status_code}"
                    total_items = f"Error: {response.status_code}"
                    
            except Exception as e:
                total_pages = f"Error: {str(e)}"
                total_items = f"Error: {str(e)}"
            
            cache_status.append({
                'seller_name': seller_name,
                'has_cached_inventory': cached_inventory is not None,
                'cached_items_count': len(cached_inventory) if cached_inventory else 0,
                'is_large_seller': is_large_seller,
                'total_pages': total_pages,
                'total_items': total_items,
                'last_updated': metadata.get('last_updated') if metadata else None,
                'can_process': not is_large_seller and total_pages != 0
            })
        
        result = {
            'registered_sellers': registered_sellers,
            'total_sellers': len(registered_sellers),
            'cache_status': cache_status,
            'processable_sellers': [s for s in cache_status if s['can_process']],
            'large_sellers': [s for s in cache_status if s['is_large_seller']]
        }
        
        # Cache the result for 5 minutes
        cache_key = f"cache_status_result_{user.id}"
        cache_service.set(cache_key, json.dumps(result), expire_seconds=300)
        
        # Also cache the full cache status for faster access
        cache_status_key = f"cache_status_full_{user.id}"
        cache_service.set(cache_status_key, json.dumps(result), expire_seconds=300)
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Error getting cache status for user {user.id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Remove from active requests
        _active_requests.pop(request_key, None)
        current_app.logger.info(f"✅ Completed cache status for user {user.id}")


