from models import db, Notification, User, Order
from datetime import datetime, timezone
from services.telegram_service import telegram_service

def send_to_telegram_if_linked(user_id, message):
    """Send a notification to Telegram if user has linked their account"""
    from models import TelegramUserLink
    
    user_link = TelegramUserLink.query.filter_by(
        user_id=user_id,
        is_active=True
    ).first()
    
    if user_link:
        try:
            telegram_service.send_message(message, user_link.telegram_user_id)
            print(f"Sent notification to Telegram for user {user_id}")
        except Exception as e:
            print(f"Error sending to Telegram for user {user_id}: {e}")

def notify_admin_to_telegram(message, notification_type):
    """Send admin notifications to all admins with linked Telegram accounts"""
    from models import TelegramUserLink, User
    
    # Get all admin users
    admins = User.query.filter_by(is_admin=True).all()
    
    for admin in admins:
        # Check if admin has linked Telegram
        user_link = TelegramUserLink.query.filter_by(
            user_id=admin.id,
            is_active=True
        ).first()
        
        if user_link:
            try:
                telegram_service.send_message(message, user_link.telegram_user_id)
                print(f"Sent {notification_type} notification to admin {admin.username} via Telegram")
            except Exception as e:
                print(f"Error sending to admin {admin.username}: {e}")

class NotificationService:
    """Service for managing notifications"""
    
    @staticmethod
    def send_notification(user_id, content, notification_type='manual', order_id=None, triggered_by_user_id=None):
        """Send a notification to a user"""
        try:
            notification = Notification(
                user_id=user_id,
                order_id=order_id,
                content=content,
                notification_type=notification_type,
                triggered_by_user_id=triggered_by_user_id
            )
            
            db.session.add(notification)
            db.session.commit()
            return notification
        except Exception as e:
            db.session.rollback()
            print(f"Error sending notification: {e}")
            return None
    
    @staticmethod
    def notify_order_created(order, creator_user):
        """Notify friends when a user creates an order"""
        try:
            # Get all friends of the creator
            friends = creator_user.friends
            if not friends:
                return
            
            content = f"{creator_user.username} a créé une nouvelle commande: {order.seller_name}"
            
            for friend in friends:
                NotificationService.send_notification(
                    user_id=friend.id,
                    content=content,
                    notification_type='order_created',
                    order_id=order.id,
                    triggered_by_user_id=creator_user.id
                )
                
                # Also send to Telegram if linked
                send_to_telegram_if_linked(friend.id, content)
            
            # Send detailed admin notification to all Telegram-linked admins
            notify_admin_to_telegram(
                message=telegram_service.format_order_created_admin(order, creator_user, len(friends)),
                notification_type='order_created'
            )
            
            print(f"Sent order creation notifications to {len(friends)} friends")
        except Exception as e:
            print(f"Error notifying order creation: {e}")
    
    @staticmethod
    def notify_status_changed(order, old_status, new_status, changed_by_user):
        """Notify participants when order status changes"""
        try:
            # Get all participants (creator + users with listings)
            participants = set()
            participants.add(order.creator_id)
            
            # Add users who have listings in this order
            for listing in order.listings:
                participants.add(listing.user_id)
            
            # Remove the user who made the change
            participants.discard(changed_by_user.id)
            
            if not participants:
                return
            
            status_names = {
                'building': 'Collecte',
                'validation': 'Validation', 
                'ordered': 'Commandé',
                'delivered': 'Livré',
                'closed': 'Distribué',
                'deleted': 'Supprimé'
            }
            
            content = f"Le statut de la commande {order.seller_name} a changé pour {status_names.get(new_status, new_status)}"
            
            for participant_id in participants:
                NotificationService.send_notification(
                    user_id=participant_id,
                    content=content,
                    notification_type='status_changed',
                    order_id=order.id,
                    triggered_by_user_id=changed_by_user.id
                )
                
                # Also send to Telegram if linked
                send_to_telegram_if_linked(participant_id, content)
            
            # Send detailed admin notification to all Telegram-linked admins
            notify_admin_to_telegram(
                message=telegram_service.format_status_changed_admin(order, old_status, new_status, changed_by_user),
                notification_type='status_changed'
            )
            
            print(f"Sent status change notifications to {len(participants)} participants")
        except Exception as e:
            print(f"Error notifying status change: {e}")
    
    @staticmethod
    def notify_disc_added(order, listing, added_by_user):
        """Notify order creator when someone adds a disc to their order"""
        try:
            # Only notify the order creator, not the person who added the disc
            if order.creator_id == added_by_user.id:
                return
            
            content = f"{added_by_user.username} a ajouté un disque à votre commande {order.seller_name}"
            
            NotificationService.send_notification(
                user_id=order.creator_id,
                content=content,
                notification_type='disc_added',
                order_id=order.id,
                triggered_by_user_id=added_by_user.id
            )
            
            # Also send to Telegram if linked
            send_to_telegram_if_linked(order.creator_id, content)
            
            # Send detailed admin notification to all Telegram-linked admins
            notify_admin_to_telegram(
                message=telegram_service.format_disc_added_admin(order, listing, added_by_user),
                notification_type='disc_added'
            )
            
            print(f"Sent disc added notification to order creator")
        except Exception as e:
            print(f"Error notifying disc added: {e}")
    
    @staticmethod
    def notify_admin_order_created(order, creator_user):
        """Notify all admins when a new order is created"""
        try:
            # Get all admin users
            admins = User.query.filter_by(is_admin=True).all()
            if not admins:
                return
            
            content = f"{creator_user.username} a créé une nouvelle commande: {order.seller_name}"
            
            for admin in admins:
                # Don't notify the creator if they're also an admin
                if admin.id != creator_user.id:
                    NotificationService.send_notification(
                        user_id=admin.id,
                        content=content,
                        notification_type='admin_order_created',
                        order_id=order.id,
                        triggered_by_user_id=creator_user.id
                    )
                    
                    # Also send to Telegram if linked
                    send_to_telegram_if_linked(admin.id, content)
            
            print(f"Sent admin order creation notifications to {len(admins)} admins")
        except Exception as e:
            print(f"Error notifying admins of order creation: {e}")
