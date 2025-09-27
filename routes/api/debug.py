"""
Debug API endpoints for testing features
"""
from flask import Blueprint, jsonify, request
from services import auth_service, wantlist_matching_service, cache_service
from datetime import datetime, timezone
import json

debug_api = Blueprint('debug_api', __name__)

@debug_api.route('/debug/wantlist-matches', methods=['GET'])
def get_wantlist_matches():
    """Get wantlist matches for the current user"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    
    try:
        results = wantlist_matching_service.get_wantlist_matches_for_user(user.id)
        return jsonify(results)
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
        inventory, metadata = wantlist_matching_service.force_refresh_seller_inventory(
            seller_name, 
            user.id, 
            user.discogs_access_token, 
            user.discogs_access_secret
        )
        
        if inventory:
            return jsonify({
                'success': True,
                'seller_name': seller_name,
                'inventory_count': len(inventory),
                'metadata': metadata
            })
        else:
            return jsonify({'error': 'Failed to refresh inventory'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@debug_api.route('/debug/cache-status', methods=['GET'])
def get_cache_status():
    """Get cache status for all sellers"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401

    user = auth_service.get_current_user()
    
    try:
        from models import Order
        open_orders = Order.query.filter(
            Order.status.in_(['building', 'validation'])
        ).all()
        
        cache_status = []
        for order in open_orders:
            seller_name = order.seller_name
            cache_key = f"seller_inventory:{seller_name}:{user.id}"
            metadata_key = f"seller_metadata:{seller_name}"
            
            # Check if cached
            cached_inventory = cache_service.get(cache_key)
            metadata = cache_service.get(metadata_key)
            
            cache_status.append({
                'seller_name': seller_name,
                'is_cached': bool(cached_inventory),
                'metadata': json.loads(metadata) if metadata else None
            })
        
        return jsonify({
            'cache_status': cache_status,
            'total_sellers': len(cache_status)
        })
        
    except Exception as e:
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


