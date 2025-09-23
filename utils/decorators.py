from functools import wraps
from flask import redirect, url_for, jsonify, request, current_app
from services import auth_service

def login_required(f):
    """Decorator that requires user to be authenticated
    
    For view functions, redirects to login page.
    For API endpoints, returns 401 JSON response.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_service.is_authenticated():
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            else:
                return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator that requires user to be admin
    
    Must be used with @login_required or equivalent auth check.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_service.is_authenticated():
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            else:
                return redirect(url_for('auth.login'))
        
        current_user = auth_service.get_current_user()
        if not current_user or not current_user.is_admin:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Admin access required'}), 403
            else:
                return redirect(url_for('views.index'))
        
        return f(*args, **kwargs)
    return decorated_function

def profile_required(f):
    """Decorator that requires user to have completed profile setup
    
    Redirects to profile setup if not completed.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_service.is_authenticated():
            return redirect(url_for('auth.login'))
        
        current_user = auth_service.get_current_user()
        if not current_user.profile_completed:
            return redirect(url_for('auth.setup_profile'))
        
        return f(*args, **kwargs)
    return decorated_function

def order_access_required(f):
    """Decorator that checks if user has access to an order
    
    Expects order_id as a parameter in the route.
    User has access if they are:
    - Creator of the order
    - Participant (has listings) in the order
    - Admin
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_service.is_authenticated():
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            else:
                return redirect(url_for('auth.login'))
        
        order_id = kwargs.get('order_id')
        if not order_id:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Order ID required'}), 400
            else:
                return redirect(url_for('views.index'))
        
        from models import Order, Listing
        order = Order.query.get_or_404(order_id)
        current_user = auth_service.get_current_user()
        
        # Check access: creator, participant, or admin
        is_creator = order.creator_id == current_user.id
        is_participant = Listing.query.filter_by(order_id=order_id, user_id=current_user.id).count() > 0
        is_admin = current_user.is_admin
        
        if not (is_creator or is_participant or is_admin):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Access denied to this order'}), 403
            else:
                return redirect(url_for('views.index'))
        
        return f(*args, **kwargs)
    return decorated_function

def order_creator_required(f):
    """Decorator that requires user to be the creator of an order
    
    Expects order_id as a parameter in the route.
    Admins also have access.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_service.is_authenticated():
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            else:
                return redirect(url_for('auth.login'))
        
        order_id = kwargs.get('order_id')
        if not order_id:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Order ID required'}), 400
            else:
                return redirect(url_for('views.index'))
        
        from models import Order
        order = Order.query.get_or_404(order_id)
        current_user = auth_service.get_current_user()
        
        if order.creator_id != current_user.id and not current_user.is_admin:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Only order creator can perform this action'}), 403
            else:
                return redirect(url_for('views.view_order', order_id=order_id))
        
        return f(*args, **kwargs)
    return decorated_function

def listing_owner_required(f):
    """Decorator that requires user to own a listing
    
    Expects listing_id as a parameter in the route.
    Admins also have access.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_service.is_authenticated():
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            else:
                return redirect(url_for('auth.login'))
        
        listing_id = kwargs.get('listing_id')
        if not listing_id:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Listing ID required'}), 400
            else:
                return redirect(url_for('views.index'))
        
        from models import Listing
        listing = Listing.query.get_or_404(listing_id)
        current_user = auth_service.get_current_user()
        
        if listing.user_id != current_user.id and not current_user.is_admin:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Only listing owner can perform this action'}), 403
            else:
                return redirect(url_for('views.view_order', order_id=listing.order_id))
        
        return f(*args, **kwargs)
    return decorated_function

def rate_limit(requests_per_minute=60):
    """Decorator for basic rate limiting
    
    This is a simple in-memory rate limiter.
    For production, consider using Flask-Limiter or Redis-based limiting.
    """
    import time
    from collections import defaultdict, deque
    
    # In-memory storage (not suitable for multiple workers)
    request_times = defaultdict(deque)
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client identifier (IP address)
            client_id = request.environ.get('REMOTE_ADDR', 'unknown')
            current_time = time.time()
            
            # Clean old requests (older than 1 minute)
            window_start = current_time - 60
            client_requests = request_times[client_id]
            
            while client_requests and client_requests[0] < window_start:
                client_requests.popleft()
            
            # Check if limit exceeded
            if len(client_requests) >= requests_per_minute:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Rate limit exceeded'}), 429
                else:
                    return "Rate limit exceeded", 429
            
            # Add current request
            client_requests.append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_json(required_fields=None):
    """Decorator to validate JSON request data
    
    Args:
        required_fields (list): List of required field names
    """
    if required_fields is None:
        required_fields = []
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({'error': 'Content-Type must be application/json'}), 400
            
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({'error': 'Invalid JSON'}), 400
            
            # Check required fields
            missing_fields = []
            for field in required_fields:
                if field not in data or data[field] is None:
                    missing_fields.append(field)
            
            if missing_fields:
                return jsonify({
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def handle_exceptions(f):
    """Decorator to handle common exceptions in API routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            current_app.logger.warning(f"ValueError in {f.__name__}: {str(e)}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"Unexpected error in {f.__name__}: {str(e)}")
            if current_app.debug:
                return jsonify({'error': str(e)}), 500
            else:
                return jsonify({'error': 'Internal server error'}), 500
    return decorated_function

def cache_response(timeout=300):
    """Decorator to cache API responses
    
    Args:
        timeout (int): Cache timeout in seconds
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from services import cache_service
            
            if not cache_service.is_available():
                return f(*args, **kwargs)
            
            # Generate cache key from route and arguments
            cache_key = f"response:{f.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_response = cache_service.get(cache_key)
            if cached_response:
                return cached_response
            
            # Execute function and cache result
            response = f(*args, **kwargs)
            
            # Only cache successful responses
            if hasattr(response, 'status_code') and response.status_code == 200:
                cache_service.set(cache_key, response.get_data(as_text=True), timeout)
            elif isinstance(response, (dict, list)):
                cache_service.set(cache_key, response, timeout)
            
            return response
        return decorated_function
    return decorator