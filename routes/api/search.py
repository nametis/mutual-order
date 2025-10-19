from flask import Blueprint, request, jsonify
from models import User
from services import auth_service

search_api = Blueprint('search_api', __name__)

@search_api.route('/search/users', methods=['GET'])
def search_users():
    """Search for users by username, mutual_order_username, profile URL, or @username"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    # Clean the query for different input formats
    clean_query = clean_search_query(query)
    
    # Search in both username and mutual_order_username
    users = User.query.filter(
        (User.mutual_order_username.ilike(f'%{clean_query}%')) |
        (User.discogs_username.ilike(f'%{clean_query}%'))
    ).limit(10).all()
    
    results = []
    for user in users:
        results.append({
            'id': user.id,
            'username': user.username,
            'mutual_order_username': user.mutual_order_username,
            'discogs_username': user.discogs_username
        })
    
    return jsonify(results)

def clean_search_query(query):
    """Clean search query to extract username from various formats"""
    import re
    
    # Remove @ prefix
    if query.startswith('@'):
        query = query[1:]
    
    # Extract username from profile URL patterns
    url_patterns = [
        r'/(?:@|u/)([^/?]+)',  # /@username or /u/username
        r'/([^/?]+)$',  # /username at end of URL
        r'username=([^&]+)',  # ?username=value
    ]
    
    for pattern in url_patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(1)
    
    # If it looks like a full URL, try to extract the last part
    if 'http' in query or '/' in query:
        # Split by / and take the last non-empty part
        parts = [p for p in query.split('/') if p and p != 'fr']
        if parts:
            return parts[-1]
    
    # Return the original query if no patterns match
    return query
