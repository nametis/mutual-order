from flask import Blueprint, jsonify, request, current_app
from services.auth_service import auth_service
from services.telegram_service import telegram_service
from datetime import datetime, timezone
import os
import logging

telegram_admin_api = Blueprint('telegram_admin_api', __name__, url_prefix='/telegram-admin')

@telegram_admin_api.route('/send-message', methods=['POST'])
def send_message():
    """Send a message to a Telegram channel or chat"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json()
    
    current_app.logger.error(f"Received data: {data}")
    current_app.logger.error(f"Content-Type: {request.content_type}")
    current_app.logger.error(f"Raw data: {request.data}")
    
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    required_fields = ['message', 'chat_id']
    for field in required_fields:
        if field not in data:
            current_app.logger.error(f"Missing field: {field}")
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    message = data['message']
    chat_id = data['chat_id']
    
    # Send message using telegram service
    success = telegram_service.send_message(message, chat_id)
    
    if success:
        return jsonify({'success': True, 'message': 'Message sent successfully'})
    else:
        return jsonify({'error': 'Failed to send message'}), 500

@telegram_admin_api.route('/commands', methods=['GET'])
def get_commands():
    """Get all bot commands"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    from models import TelegramBotCommand
    
    commands = TelegramBotCommand.query.order_by(TelegramBotCommand.command).all()
    
    return jsonify([cmd.to_dict() for cmd in commands])

@telegram_admin_api.route('/commands', methods=['POST'])
def create_command():
    """Create a new bot command"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    from models import db, TelegramBotCommand
    
    data = request.get_json()
    
    if 'command' not in data or 'response' not in data:
        return jsonify({'error': 'Missing required fields: command, response'}), 400
    
    command_text = data['command']
    response = data['response']
    enabled = data.get('enabled', True)
    
    # Check if command already exists
    existing = TelegramBotCommand.query.filter_by(command=command_text).first()
    if existing:
        return jsonify({'error': 'Command already exists'}), 400
    
    try:
        new_command = TelegramBotCommand(
            command=command_text,
            response=response,
            enabled=enabled
        )
        db.session.add(new_command)
        db.session.commit()
        
        return jsonify({'success': True, 'command': new_command.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@telegram_admin_api.route('/commands/<int:command_id>', methods=['PUT'])
def update_command(command_id):
    """Update an existing bot command"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    from models import db, TelegramBotCommand
    
    command = TelegramBotCommand.query.get_or_404(command_id)
    data = request.get_json()
    
    try:
        if 'command' in data:
            # Check for duplicate
            existing = TelegramBotCommand.query.filter_by(command=data['command']).first()
            if existing and existing.id != command_id:
                return jsonify({'error': 'Command already exists'}), 400
            command.command = data['command']
        
        if 'response' in data:
            command.response = data['response']
        
        if 'enabled' in data:
            command.enabled = data['enabled']
        
        command.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({'success': True, 'command': command.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@telegram_admin_api.route('/commands/<int:command_id>', methods=['DELETE'])
def delete_command(command_id):
    """Delete a bot command"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    from models import db, TelegramBotCommand
    
    command = TelegramBotCommand.query.get_or_404(command_id)
    
    try:
        db.session.delete(command)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@telegram_admin_api.route('/channels', methods=['GET'])
def get_channels():
    """Get all Telegram channels"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    from models import TelegramChannel
    
    channels = TelegramChannel.query.all()
    
    return jsonify([ch.to_dict() for ch in channels])

@telegram_admin_api.route('/channels', methods=['POST'])
def create_channel():
    """Create a new Telegram channel entry"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    from models import db, TelegramChannel
    
    data = request.get_json()
    
    if 'name' not in data or 'chat_id' not in data:
        return jsonify({'error': 'Missing required fields: name, chat_id'}), 400
    
    try:
        new_channel = TelegramChannel(
            name=data['name'],
            chat_id=data['chat_id'],
            description=data.get('description'),
            is_active=data.get('is_active', True)
        )
        db.session.add(new_channel)
        db.session.commit()
        
        return jsonify({'success': True, 'channel': new_channel.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@telegram_admin_api.route('/interactions', methods=['GET'])
def get_interactions():
    """Get all bot interactions for monitoring"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    from models import TelegramInteraction
    
    limit = request.args.get('limit', 50, type=int)
    interaction_type = request.args.get('type')  # Optional filter by type
    
    query = TelegramInteraction.query.order_by(TelegramInteraction.created_at.desc())
    
    if interaction_type:
        query = query.filter_by(interaction_type=interaction_type)
    
    interactions = query.limit(limit).all()
    
    return jsonify([i.to_dict() for i in interactions])

@telegram_admin_api.route('/linked-users', methods=['GET'])
def get_linked_users():
    """Get all users with linked Telegram accounts"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = auth_service.get_current_user()
    if not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    from models import TelegramUserLink
    
    links = TelegramUserLink.query.filter_by(is_active=True).all()
    
    return jsonify([link.to_dict() for link in links])

@telegram_admin_api.route('/generate-linking-qr', methods=['GET'])
def generate_linking_qr():
    """Generate a QR code for linking Telegram account"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    from services.qr_service import qr_service
    from flask import send_file
    import io
    import base64
    
    user = auth_service.get_current_user()
    
    # Generate token and deep link
    token = qr_service.generate_linking_token(user.id)
    bot_username = 'mutual_order_bot'  # Your bot username
    deep_link = f"https://t.me/{bot_username}?start={token}"
    
    # Generate QR code
    qr_image = qr_service.generate_qr_code(deep_link)
    
    # Convert to base64 for inline display
    qr_base64 = base64.b64encode(qr_image).decode('utf-8')
    
    return jsonify({
        'qr_code': f'data:image/png;base64,{qr_base64}',
        'token': token,
        'deep_link': deep_link
    })

@telegram_admin_api.route('/link-account', methods=['POST'])
def link_telegram_account():
    """Link a Mutual Order account to a Telegram account"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    from models import db, TelegramUserLink, User
    
    data = request.get_json()
    
    if 'telegram_user_id' not in data:
        return jsonify({'error': 'Missing telegram_user_id'}), 400
    
    telegram_user_id = str(data['telegram_user_id'])
    telegram_username = data.get('telegram_username')
    telegram_first_name = data.get('telegram_first_name')
    telegram_last_name = data.get('telegram_last_name')
    
    try:
        user = auth_service.get_current_user()
        
        # Check if already linked
        existing = TelegramUserLink.query.filter_by(
            telegram_user_id=telegram_user_id
        ).first()
        
        if existing:
            return jsonify({'error': 'This Telegram account is already linked to another user'}), 400
        
        # Check if user already has a link
        user_link = TelegramUserLink.query.filter_by(user_id=user.id).first()
        
        if user_link:
            # Update existing link
            user_link.telegram_user_id = telegram_user_id
            user_link.telegram_username = telegram_username
            user_link.telegram_first_name = telegram_first_name
            user_link.telegram_last_name = telegram_last_name
            user_link.is_active = True
            user_link.last_seen = datetime.now(timezone.utc)
        else:
            # Create new link
            user_link = TelegramUserLink(
                user_id=user.id,
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
                telegram_first_name=telegram_first_name,
                telegram_last_name=telegram_last_name
            )
            db.session.add(user_link)
        
        db.session.commit()
        
        return jsonify({'success': True, 'link': user_link.to_dict()})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error linking account: {e}")
        return jsonify({'error': str(e)}), 500

@telegram_admin_api.route('/unlink-account', methods=['POST'])
def unlink_telegram_account():
    """Unlink a Telegram account from a Mutual Order account"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    from models import db, TelegramUserLink
    
    try:
        user = auth_service.get_current_user()
        user_link = TelegramUserLink.query.filter_by(user_id=user.id).first()
        
        if user_link:
            user_link.is_active = False
            db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@telegram_admin_api.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming messages from Telegram webhook"""
    from models import db, TelegramBotCommand, TelegramUserLink, TelegramInteraction
    
    try:
        update = request.get_json()
        
        # Handle incoming messages
        if 'message' in update:
            message = update['message']
            chat = message.get('chat', {})
            chat_id = str(chat.get('id'))
            text = message.get('text', '')
            from_user = message.get('from', {})
            
            # Extract user info
            telegram_user_id = str(from_user.get('id'))
            telegram_username = from_user.get('username')
            first_name = from_user.get('first_name')
            last_name = from_user.get('last_name')
            
            # Update last_seen for linked users
            if telegram_user_id:
                user_link = TelegramUserLink.query.filter_by(
                    telegram_user_id=telegram_user_id, 
                    is_active=True
                ).first()
                if user_link:
                    user_link.last_seen = datetime.now(timezone.utc)
                    db.session.commit()
            
            # Check if it's a command
            if text.startswith('/'):
                command = text.split()[0]  # Get command without arguments
                
                # Special handler for /link command or start with token
                if command == '/link':
                    # Send user their Telegram information
                    user_id = str(from_user.get('id'))
                    username = from_user.get('username', 'Not set')
                    first_name = from_user.get('first_name', '')
                    last_name = from_user.get('last_name', '')
                    
                    message = (
                        f"<b>Your Telegram Information:</b>\n\n"
                        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
                        f"📝 <b>Username:</b> @{username}\n"
                        f"📛 <b>First Name:</b> {first_name}\n"
                        f"📛 <b>Last Name:</b> {last_name}\n\n"
                        f"Use this information to link your account at:\n"
                        f"🔗 https://mutual-order.ddns.net/notification-debug"
                    )
                    
                    telegram_service.send_message(message, chat_id)
                    
                    # Log the /link command interaction
                    interaction = TelegramInteraction(
                        chat_id=chat_id,
                        user_id=telegram_user_id,
                        username=telegram_username,
                        first_name=first_name,
                        last_name=last_name,
                        message_text=text,
                        command='/link',
                        response_sent=message,
                        interaction_type='command'
                    )
                    db.session.add(interaction)
                    db.session.commit()
                    
                    return jsonify({'ok': True})
                
                # Handle /start with token for automatic linking
                if command == '/start' and len(text.split()) > 1:
                    token = text.split()[1]  # Get the token after /start
                    
                    # Verify token and get user_id
                    from services.qr_service import qr_service
                    mutual_user_id = qr_service.verify_token(token)
                    
                    if mutual_user_id:
                        # Automatically link accounts
                        from models import db, TelegramUserLink
                        
                        telegram_user_id = str(from_user.get('id'))
                        telegram_username = from_user.get('username')
                        telegram_first_name = from_user.get('first_name')
                        telegram_last_name = from_user.get('last_name')
                        
                        # Check if already linked
                        existing = TelegramUserLink.query.filter_by(
                            telegram_user_id=telegram_user_id
                        ).first()
                        
                        if existing:
                            message = "This Telegram account is already linked to another Mutual Order account."
                        else:
                            # Create new link
                            user_link = TelegramUserLink(
                                user_id=mutual_user_id,
                                telegram_user_id=telegram_user_id,
                                telegram_username=telegram_username,
                                telegram_first_name=telegram_first_name,
                                telegram_last_name=telegram_last_name
                            )
                            db.session.add(user_link)
                            db.session.commit()
                            
                            message = (
                                f"✅ <b>Account linked successfully!</b>\n\n"
                                f"You will now receive notifications from Mutual Order on Telegram."
                            )
                        
                        telegram_service.send_message(message, chat_id)
                        
                        # Log the auto-linking interaction
                        interaction = TelegramInteraction(
                            chat_id=chat_id,
                            user_id=telegram_user_id,
                            username=telegram_username,
                            first_name=telegram_first_name,
                            last_name=telegram_last_name,
                            message_text=text,
                            command='/start',
                            response_sent=message,
                            interaction_type='auto_linking',
                            linked_user_id=mutual_user_id
                        )
                        db.session.add(interaction)
                        db.session.commit()
                        
                        return jsonify({'ok': True})
                    else:
                        # Invalid or expired token
                        message = (
                            "❌ Invalid or expired linking token.\n\n"
                            "Please generate a new QR code at:\n"
                            "🔗 https://mutual-order.ddns.net/notification-debug"
                        )
                        telegram_service.send_message(message, chat_id)
                        return jsonify({'ok': True})
                
                # Find matching bot command
                bot_command = TelegramBotCommand.query.filter_by(command=command, enabled=True).first()
                
                if bot_command:
                    # Send response - chat_id needs to be string
                    telegram_service.send_message(bot_command.response, chat_id)
                    
                    # Log the interaction
                    interaction = TelegramInteraction(
                        chat_id=chat_id,
                        user_id=telegram_user_id,
                        username=telegram_username,
                        first_name=first_name,
                        last_name=last_name,
                        message_text=text,
                        command=command,
                        response_sent=bot_command.response,
                        interaction_type='command'
                    )
                    db.session.add(interaction)
                    db.session.commit()
                
                return jsonify({'ok': True})
        
        return jsonify({'ok': True})
    except Exception as e:
        current_app.logger.error(f"Error handling webhook: {e}")
        return jsonify({'error': str(e)}), 500
