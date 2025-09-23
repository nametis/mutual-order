from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import pytz
from models import db, Order, OrderChat, ChatReadStatus
from services import auth_service

chat_api = Blueprint('chat_api', __name__)

# Paris timezone for display
PARIS_TZ = pytz.timezone('Europe/Paris')

def utc_to_paris(utc_dt):
    """Convert UTC datetime to Paris time"""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(PARIS_TZ)

@chat_api.route('/orders/<int:order_id>/chat/messages', methods=['GET'])
def get_chat_messages(order_id):
    """Get chat messages for an order"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    # Verify user has access to this order (is a participant)
    user_listing_count = order.listings.filter_by(user_id=current_user.id).count()
    if user_listing_count == 0 and order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied to this order chat'}), 403
    
    messages = OrderChat.query.filter_by(order_id=order_id).order_by(OrderChat.created_at.asc()).all()
    
    messages_data = []
    for message in messages:
        messages_data.append(message.to_dict(
            current_user_id=current_user.id,
            timezone_func=utc_to_paris
        ))
    
    return jsonify(messages_data)

@chat_api.route('/orders/<int:order_id>/chat/send', methods=['POST'])
def send_chat_message(order_id):
    """Send a chat message"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    # Verify user has access to this order
    user_listing_count = order.listings.filter_by(user_id=current_user.id).count()
    if user_listing_count == 0 and order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied to this order chat'}), 403
    
    data = request.get_json()
    message_content = data.get('message', '').strip()
    
    if not message_content:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    if len(message_content) > 500:
        return jsonify({'error': 'Message too long (max 500 characters)'}), 400
    
    try:
        chat_message = OrderChat(
            order_id=order_id,
            user_id=current_user.id,
            message=message_content
        )
        db.session.add(chat_message)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': chat_message.to_dict(
                current_user_id=current_user.id,
                timezone_func=utc_to_paris
            )
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to send message'}), 500

@chat_api.route('/orders/<int:order_id>/chat/unread', methods=['GET'])
def get_unread_chat_count(order_id):
    """Get unread message count for an order"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    # Verify user has access to this order
    user_listing_count = order.listings.filter_by(user_id=current_user.id).count()
    if user_listing_count == 0 and order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied to this order chat'}), 403
    
    # Get last read timestamp for this user
    read_status = ChatReadStatus.query.filter_by(
        user_id=current_user.id,
        order_id=order_id
    ).first()
    
    if read_status:
        last_read_at = read_status.last_read_at
    else:
        # If no read status exists, consider everything unread
        last_read_at = datetime.min.replace(tzinfo=timezone.utc)
    
    # Count messages newer than last read time
    unread_count = OrderChat.query.filter(
        OrderChat.order_id == order_id,
        OrderChat.created_at > last_read_at,
        OrderChat.user_id != current_user.id  # Don't count own messages as unread
    ).count()
    
    return jsonify({'unread_count': unread_count})

@chat_api.route('/orders/<int:order_id>/chat/mark_read', methods=['POST'])
def mark_chat_messages_read(order_id):
    """Mark chat messages as read for current user"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    # Verify user has access to this order
    user_listing_count = order.listings.filter_by(user_id=current_user.id).count()
    if user_listing_count == 0 and order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied to this order chat'}), 403
    
    try:
        # Update or create read status
        read_status = ChatReadStatus.query.filter_by(
            user_id=current_user.id,
            order_id=order_id
        ).first()
        
        if read_status:
            read_status.mark_read()
        else:
            read_status = ChatReadStatus(
                user_id=current_user.id,
                order_id=order_id,
                last_read_at=datetime.now(timezone.utc)
            )
            db.session.add(read_status)
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to mark messages as read'}), 500

@chat_api.route('/orders/<int:order_id>/chat/history', methods=['GET'])
def get_chat_history(order_id):
    """Get paginated chat history"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = auth_service.get_current_user()
    
    # Verify user has access to this order
    user_listing_count = order.listings.filter_by(user_id=current_user.id).count()
    if user_listing_count == 0 and order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied to this order chat'}), 403
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)  # Max 100 per page
    
    # Get paginated messages
    messages_query = OrderChat.query.filter_by(order_id=order_id).order_by(OrderChat.created_at.desc())
    paginated_messages = messages_query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    messages_data = []
    for message in reversed(paginated_messages.items):  # Reverse to show oldest first within page
        messages_data.append(message.to_dict(
            current_user_id=current_user.id,
            timezone_func=utc_to_paris
        ))
    
    return jsonify({
        'messages': messages_data,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': paginated_messages.total,
            'pages': paginated_messages.pages,
            'has_prev': paginated_messages.has_prev,
            'has_next': paginated_messages.has_next
        }
    })