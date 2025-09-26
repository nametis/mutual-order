from flask import Blueprint, request, jsonify, current_app
from services import auth_service, wantlist_service
from models import db, User, WantlistItem, WantlistReference

# Create wantlist API blueprint
wantlist_api = Blueprint('wantlist_api', __name__)

@wantlist_api.route('/wantlist/sync', methods=['POST'])
def sync_wantlist():
    """Sync user's wantlist from Discogs"""
    try:
        if not auth_service.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        user = auth_service.get_current_user()
        force_refresh = request.json.get('force_refresh', False) if request.is_json else False
        
        # Sync wantlist from Discogs
        wantlist_items = wantlist_service.sync_user_wantlist(user.id, force_refresh)
        
        return jsonify({
            'success': True,
            'message': f'Synced {len(wantlist_items)} wantlist items',
            'items': wantlist_items
        })
        
    except Exception as e:
        current_app.logger.error(f"Error syncing wantlist: {e}")
        return jsonify({'error': str(e)}), 500

@wantlist_api.route('/wantlist', methods=['GET'])
def get_wantlist():
    """Get user's wantlist from local database"""
    try:
        if not auth_service.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        user = auth_service.get_current_user()
        wantlist_items = wantlist_service.get_user_wantlist(user.id)
        
        return jsonify({
            'success': True,
            'items': wantlist_items,
            'count': len(wantlist_items)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting wantlist: {e}")
        return jsonify({'error': str(e)}), 500

@wantlist_api.route('/wantlist/references', methods=['GET'])
def get_wantlist_references():
    """Get references to user's wantlist items in seller listings"""
    try:
        if not auth_service.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        user = auth_service.get_current_user()
        order_id = request.args.get('order_id', type=int)
        
        # Find references in listings
        references = wantlist_service.find_references_in_listings(user.id, order_id)
        
        return jsonify({
            'success': True,
            'references': references,
            'count': len(references)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting wantlist references: {e}")
        return jsonify({'error': str(e)}), 500

@wantlist_api.route('/wantlist/stats', methods=['GET'])
def get_wantlist_stats():
    """Get statistics about user's wantlist and references"""
    try:
        if not auth_service.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        user = auth_service.get_current_user()
        stats = wantlist_service.get_wantlist_stats(user.id)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting wantlist stats: {e}")
        return jsonify({'error': str(e)}), 500

@wantlist_api.route('/wantlist/references/<int:listing_id>', methods=['GET'])
def get_listing_wantlist_references(listing_id):
    """Get wantlist references for a specific listing"""
    try:
        if not auth_service.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        user = auth_service.get_current_user()
        
        # Get references for this specific listing
        references = WantlistReference.query.filter_by(
            listing_id=listing_id,
            user_id=user.id
        ).all()
        
        return jsonify({
            'success': True,
            'references': [ref.to_dict() for ref in references],
            'count': len(references)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting listing wantlist references: {e}")
        return jsonify({'error': str(e)}), 500

@wantlist_api.route('/wantlist/cleanup', methods=['POST'])
def cleanup_old_references():
    """Clean up old wantlist references (admin only)"""
    try:
        if not auth_service.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        user = auth_service.get_current_user()
        if not user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        days = request.json.get('days', 30) if request.is_json else 30
        deleted_count = wantlist_service.cleanup_old_references(days)
        
        return jsonify({
            'success': True,
            'message': f'Cleaned up {deleted_count} old references',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        current_app.logger.error(f"Error cleaning up old references: {e}")
        return jsonify({'error': str(e)}), 500

@wantlist_api.route('/wantlist/item/<int:item_id>', methods=['DELETE'])
def delete_wantlist_item(item_id):
    """Delete a wantlist item"""
    try:
        if not auth_service.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        user = auth_service.get_current_user()
        
        # Find the wantlist item
        item = WantlistItem.query.filter_by(id=item_id, user_id=user.id).first()
        if not item:
            return jsonify({'error': 'Wantlist item not found'}), 404
        
        # Delete associated references first
        WantlistReference.query.filter_by(wantlist_item_id=item.id).delete()
        
        # Delete the item
        db.session.delete(item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Wantlist item deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting wantlist item: {e}")
        return jsonify({'error': str(e)}), 500

@wantlist_api.route('/wantlist/reference/<int:reference_id>', methods=['DELETE'])
def delete_wantlist_reference(reference_id):
    """Delete a wantlist reference"""
    try:
        if not auth_service.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        user = auth_service.get_current_user()
        
        # Find the reference
        reference = WantlistReference.query.filter_by(id=reference_id, user_id=user.id).first()
        if not reference:
            return jsonify({'error': 'Reference not found'}), 404
        
        # Delete the reference
        db.session.delete(reference)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Reference deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting wantlist reference: {e}")
        return jsonify({'error': str(e)}), 500
