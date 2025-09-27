from flask import Blueprint
from .orders import orders_api
from .listings import listings_api
from .chat import chat_api
from .users import users_api
from .wantlist import wantlist_api
from .debug import debug_api

# Create main API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Register all API sub-blueprints
api_bp.register_blueprint(orders_api)
api_bp.register_blueprint(listings_api)
api_bp.register_blueprint(chat_api)
api_bp.register_blueprint(users_api)
api_bp.register_blueprint(wantlist_api)
api_bp.register_blueprint(debug_api)

__all__ = ['api_bp']