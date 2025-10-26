from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

# Import all models to ensure they're registered
from .user import User
from .order import Order, UserValidation
from .listing import Listing
from .chat import OrderChat, ChatReadStatus
from .favorite_seller import FavoriteSeller
from .friend import Friend
from .friend_request import FriendRequest
from .wantlist import WantlistItem, WantlistReference
from .notification import Notification
from .payment import UserPayment
from .telegram_bot import TelegramBotCommand, TelegramChannel, TelegramInteraction
from .telegram_user_link import TelegramUserLink
from .telegram_token import TelegramLinkToken

__all__ = ['db', 'User', 'Order', 'UserValidation', 'Listing', 'OrderChat', 'ChatReadStatus', 'FavoriteSeller', 'Friend', 'FriendRequest', 'WantlistItem', 'WantlistReference', 'Notification', 'UserPayment', 'TelegramBotCommand', 'TelegramChannel', 'TelegramUserLink', 'TelegramLinkToken', 'TelegramInteraction']