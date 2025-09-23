from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

# Import all models to ensure they're registered
from .user import User
from .order import Order, UserValidation
from .listing import Listing
from .chat import OrderChat, ChatReadStatus

__all__ = ['db', 'User', 'Order', 'UserValidation', 'Listing', 'OrderChat', 'ChatReadStatus']