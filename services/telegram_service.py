import os
import requests
from typing import Optional

class TelegramService:
    """Service for sending Telegram notifications"""
    
    def __init__(self):
        # Get Telegram configuration from environment
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        
        if not self.bot_token:
            import logging
            logging.warning("WARNING: Telegram bot token not configured. Telegram notifications will be disabled.")
    
    def send_message(self, message: str, chat_id: str = None, parse_mode: str = 'HTML') -> bool:
        """
        Send a message to a Telegram chat (channel, group, or private)
        
        Args:
            message: The message to send
            chat_id: Target chat ID (defaults to configured chat_id)
            parse_mode: HTML or Markdown formatting
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.bot_token:
            return False
        
        # chat_id is required
        target_chat_id = chat_id
        
        if not target_chat_id:
            return False
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        try:
            response = requests.post(
                url,
                json={
                    'chat_id': target_chat_id,
                    'text': message,
                    'parse_mode': parse_mode
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    def format_order_created_admin(self, order, creator_user, friends_count: int = 0):
        """Format admin notification for new order (returns formatted message)"""
        try:
            message = (
                f"🔔 <b>Nouvelle commande créée</b>\n\n"
                f"👤 <b>Créateur:</b> {creator_user.username}\n"
                f"🏪 <b>Vendeur:</b> {order.seller_name}\n"
                f"📍 <b>Ville:</b> {order.city}\n"
                f"🔗 <b>ID Commande:</b> {order.id}\n"
                f"👥 <b>Amis notifiés:</b> {friends_count}"
            )
            
            if order.deadline:
                message += f"\n📅 <b>Date limite:</b> {order.deadline.strftime('%d/%m/%Y')}"
            
            if order.distribution_method:
                message += f"\n📦 <b>Distribution:</b> {order.distribution_method}"
            
            # Add link to order
            order_url = f"{os.environ.get('BASE_URL', 'http://localhost:5000')}/order/{order.id}"
            message += f"\n\n🔗 <a href='{order_url}'>Voir la commande</a>"
            
            return message
        except Exception as e:
            import logging
            logging.error(f"Error formatting Telegram order created notification: {e}")
            return ""
    
    def format_status_changed_admin(self, order, old_status, new_status, changed_by_user):
        """Format admin notification for status change (returns formatted message)"""
        try:
            status_emoji = {
                'building': '📋',
                'payment': '💳',
                'transport': '🚚',
                'distribution': '📦',
                'deleted': '🗑️'
            }
            
            status_names = {
                'building': 'Collecte',
                'payment': 'Paiement',
                'transport': 'Transport',
                'distribution': 'Distribution',
                'deleted': 'Supprimé'
            }
            
            emoji = status_emoji.get(new_status, '🔔')
            status_display = status_names.get(new_status, new_status)
            
            message = (
                f"{emoji} <b>Statut de commande modifié</b>\n\n"
                f"👤 <b>Modifié par:</b> {changed_by_user.username}\n"
                f"🏪 <b>Vendeur:</b> {order.seller_name}\n"
                f"📍 <b>Ville:</b> {order.city}\n"
                f"🔗 <b>ID Commande:</b> {order.id}\n"
                f"📋 <b>Ancien statut:</b> {status_names.get(old_status, old_status)}\n"
                f"✨ <b>Nouveau statut:</b> {status_display}"
            )
            
            # Add link to order
            order_url = f"{os.environ.get('BASE_URL', 'http://localhost:5000')}/order/{order.id}"
            message += f"\n\n🔗 <a href='{order_url}'>Voir la commande</a>"
            
            return message
        except Exception as e:
            import logging
            logging.error(f"Error formatting Telegram status changed notification: {e}")
            return ""
    
    def format_disc_added_admin(self, order, listing, added_by_user):
        """Format admin notification for disc added (returns formatted message)"""
        try:
            message = (
                f"💿 <b>Disque ajouté</b>\n\n"
                f"👤 <b>Ajouté par:</b> {added_by_user.username}\n"
                f"🏪 <b>Vendeur:</b> {order.seller_name}\n"
                f"💿 <b>Disque:</b> {listing.title}\n"
                f"💰 <b>Prix:</b> {listing.price_value:.2f}€\n"
                f"🔗 <b>ID Commande:</b> {order.id}"
            )
            
            # Add link to order
            order_url = f"{os.environ.get('BASE_URL', 'http://localhost:5000')}/order/{order.id}"
            message += f"\n\n🔗 <a href='{order_url}'>Voir la commande</a>"
            
            return message
        except Exception as e:
            import logging
            logging.error(f"Error formatting Telegram disc added notification: {e}")
            return ""

# Create singleton instance
telegram_service = TelegramService()
