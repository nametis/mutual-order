from flask import Blueprint, jsonify, request
from services.auth_service import auth_service
from services.notification_service import send_to_telegram_if_linked
from datetime import datetime, timezone

notifications_api = Blueprint('notifications_api', __name__)

@notifications_api.route('/notifications', methods=['GET'])
def get_notifications():
    """Get notifications for current user"""
    from models import db, Notification
    
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    
    # Get query parameters
    limit = request.args.get('limit', 10, type=int)
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    
    # Build query
    query = Notification.query.filter_by(user_id=user.id)
    
    if unread_only:
        query = query.filter_by(is_read=False)
    
    # Order by most recent first
    query = query.order_by(Notification.created_at.desc())
    
    # Apply limit
    notifications = query.limit(limit).all()
    
    return jsonify([notification.to_dict() for notification in notifications])

@notifications_api.route('/notifications/unread-count', methods=['GET'])
def get_unread_count():
    """Get unread notification count for current user"""
    from models import Notification
    
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    
    return jsonify({'unread_count': count})

@notifications_api.route('/notifications/<int:notification_id>/read', methods=['POST'])
def mark_as_read(notification_id):
    """Mark a notification as read"""
    from models import db, Notification
    
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    notification = Notification.query.filter_by(id=notification_id, user_id=user.id).first()
    
    if not notification:
        return jsonify({'error': 'Notification not found'}), 404
    
    try:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@notifications_api.route('/notifications/mark-all-read', methods=['POST'])
def mark_all_as_read():
    """Mark all notifications as read for current user"""
    from models import db, Notification
    
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    
    try:
        Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@notifications_api.route('/notifications/send', methods=['POST'])
def send_notification():
    """Send a notification (admin only)"""
    from models import db, Notification, User
    
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'content']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Find target user
    target_user = User.query.filter_by(mutual_order_username=data['username']).first()
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Create notification
    try:
        notification = Notification(
            user_id=target_user.id,
            order_id=data.get('order_id'),
            content=data['content'],
            notification_type=data.get('type', 'manual'),
            triggered_by_user_id=user.id
        )
        
        db.session.add(notification)
        db.session.commit()
        
        # Also send to Telegram if user has linked account
        send_to_telegram_if_linked(target_user.id, data['content'])
        
        return jsonify({'success': True, 'notification_id': notification.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@notifications_api.route('/notifications/templates', methods=['GET'])
def get_notification_templates():
    """Get notification templates (admin only)"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    templates = [
        {
            'id': 'order_created',
            'content': 'Une nouvelle commande a été créée par {username}',
            'description': 'Notification when a friend creates an order'
        },
        {
            'id': 'status_changed',
            'content': 'Le statut de la commande {order_name} a changé pour {status}',
            'description': 'Notification when order status changes'
        },
        {
            'id': 'disc_added',
            'content': '{username} a ajouté un disque à votre commande {order_name}',
            'description': 'Notification when someone adds a disc to your order'
        },
        {
            'id': 'manual',
            'content': '{message}',
            'description': 'Custom notification message'
        }
    ]
    
    return jsonify(templates)
