import re
import pytz
from datetime import datetime, timezone
from flask import current_app

# Paris timezone
PARIS_TZ = pytz.timezone('Europe/Paris')

def paris_now():
    """Get current time in Paris timezone"""
    return datetime.now(PARIS_TZ)

def utc_to_paris(utc_dt):
    """Convert UTC datetime to Paris time"""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(PARIS_TZ)

def format_date_french(date_obj):
    """Format date in French format (DD/MM/YYYY)"""
    if not date_obj:
        return ""
    
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
        except:
            return date_obj
    
    # Convert to Paris time if it's a UTC datetime
    if date_obj.tzinfo:
        date_obj = utc_to_paris(date_obj)
    
    return date_obj.strftime('%d/%m/%Y')

def format_datetime_french(datetime_obj):
    """Format datetime in French format (DD/MM/YYYY HH:MM)"""
    if not datetime_obj:
        return ""
    
    if isinstance(datetime_obj, str):
        try:
            datetime_obj = datetime.fromisoformat(datetime_obj.replace('Z', '+00:00'))
        except:
            return datetime_obj
    
    # Convert to Paris time if it's a UTC datetime
    if datetime_obj.tzinfo:
        datetime_obj = utc_to_paris(datetime_obj)
    
    return datetime_obj.strftime('%d/%m/%Y %H:%M')

def extract_listing_id(url):
    """Extract listing ID from Discogs URL
    
    Args:
        url (str): Discogs listing URL
        
    Returns:
        str or None: Listing ID if found, None otherwise
    """
    if not url:
        return None
    
    match = re.search(r"/sell/item/(\d+)", url)
    return match.group(1) if match else None

def validate_discogs_url(url):
    """Validate if URL is a valid Discogs listing URL
    
    Args:
        url (str): URL to validate
        
    Returns:
        bool: True if valid Discogs listing URL
    """
    if not url:
        return False
    
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        return False
    
    # Check if it's a Discogs URL with listing ID
    return bool(re.search(r"discogs\.com/sell/item/\d+", url))

def format_currency(amount, currency='EUR'):
    """Format currency amount
    
    Args:
        amount (float): Amount to format
        currency (str): Currency code
        
    Returns:
        str: Formatted currency string
    """
    if amount is None:
        return "0€"
    
    if currency == 'EUR':
        return f"{amount:.2f}€"
    elif currency == 'USD':
        return f"${amount:.2f}"
    elif currency == 'GBP':
        return f"£{amount:.2f}"
    else:
        return f"{amount:.2f} {currency}"

def truncate_text(text, max_length=50, suffix="..."):
    """Truncate text to specified length
    
    Args:
        text (str): Text to truncate
        max_length (int): Maximum length
        suffix (str): Suffix to add if truncated
        
    Returns:
        str: Truncated text
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def get_condition_class(condition):
    """Get CSS class for record condition
    
    Args:
        condition (str): Record condition
        
    Returns:
        str: CSS class name
    """
    if not condition:
        return 'bg-gray-100 text-gray-800'
    
    condition_lower = condition.lower()
    
    if 'mint' in condition_lower and 'near' not in condition_lower:
        return 'bg-green-100 text-green-800'
    elif 'near mint' in condition_lower:
        return 'bg-emerald-100 text-emerald-800'
    elif 'very good plus' in condition_lower:
        return 'bg-yellow-100 text-yellow-800'
    elif 'very good' in condition_lower:
        return 'bg-orange-100 text-orange-800'
    elif 'good' in condition_lower:
        return 'bg-red-100 text-red-800'
    else:
        return 'bg-gray-100 text-gray-800'

def get_short_condition(condition):
    """Get short form of condition
    
    Args:
        condition (str): Full condition text
        
    Returns:
        str: Short condition code
    """
    if not condition:
        return ''
    
    # Extract from parentheses first (e.g. "Very Good Plus (VG+)" => "VG+")
    match = re.search(r'\(([^)]+)\)', condition)
    if match:
        return match.group(1)
    
    # Fallback mappings
    condition_lower = condition.lower()
    if 'mint' in condition_lower and 'near' not in condition_lower:
        return 'M'
    elif 'near mint' in condition_lower:
        return 'NM'
    elif 'very good plus' in condition_lower:
        return 'VG+'
    elif 'very good' in condition_lower:
        return 'VG'
    elif 'good plus' in condition_lower:
        return 'G+'
    elif 'good' in condition_lower:
        return 'G'
    elif 'fair' in condition_lower:
        return 'F'
    elif 'poor' in condition_lower:
        return 'P'
    
    return condition[:3].upper()  # Fallback: first 3 chars

def get_status_info(status):
    """Get status display information
    
    Args:
        status (str): Order status
        
    Returns:
        dict: Status info with text and CSS class
    """
    status_map = {
        'building': {
            'text': '⛏️ COLLECTE',
            'class': 'bg-yellow-100 text-yellow-800'
        },
        'payment': {
            'text': '💳 PAIEMENTS',
            'class': 'bg-blue-100 text-blue-800'
        },
        'transport': {
            'text': '🚚 TRANSPORT',
            'class': 'bg-green-100 text-green-800'
        },
        'distribution': {
            'text': '🎁 DISTRIBUTION',
            'class': 'bg-purple-100 text-purple-800'
        }
    }
    
    return status_map.get(status, {
        'text': status.upper(),
        'class': 'bg-gray-100 text-gray-800'
    })

def calculate_time_remaining(deadline):
    """Calculate time remaining until deadline
    
    Args:
        deadline (datetime): Deadline datetime
        
    Returns:
        str: Human readable time remaining
    """
    if not deadline:
        return ''
    
    if isinstance(deadline, str):
        try:
            deadline = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
        except:
            return ''
    
    now = datetime.now(timezone.utc)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    
    diff = deadline - now
    
    if diff.total_seconds() <= 0:
        return 'Expiré'
    
    days = diff.days
    hours = diff.seconds // 3600
    
    if days > 0:
        return f"{days}j {hours}h"
    elif hours > 0:
        return f"{hours}h"
    else:
        return '<1h'

def safe_float(value, default=0.0):
    """Safely convert value to float
    
    Args:
        value: Value to convert
        default (float): Default value if conversion fails
        
    Returns:
        float: Converted value or default
    """
    if value is None:
        return default
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Safely convert value to integer
    
    Args:
        value: Value to convert
        default (int): Default value if conversion fails
        
    Returns:
        int: Converted value or default
    """
    if value is None:
        return default
    
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def sanitize_filename(filename):
    """Sanitize filename for safe use
    
    Args:
        filename (str): Original filename
        
    Returns:
        str: Sanitized filename
    """
    if not filename:
        return "unknown"
    
    # Remove/replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'\s+', '_', filename)  # Replace spaces with underscores
    filename = filename.strip('.')  # Remove leading/trailing dots
    
    return filename[:100]  # Limit length

def generate_order_summary_text(order):
    """Generate text summary of an order for sharing/export
    
    Args:
        order: Order object
        
    Returns:
        str: Text summary
    """
    lines = [
        f"=== COMMANDE {order.seller_name.upper()} ===",
        f"Créateur: {order.creator.username}",
        f"Statut: {get_status_info(order.status)['text']}",
        f"Total: {format_currency(order.total_with_fees)}",
        f"Participants: {order.participants_count}",
        f"Disques: {order.listings.filter_by(status='For Sale').count()}",
        ""
    ]
    
    if order.deadline:
        lines.append(f"Échéance: {format_date_french(order.deadline)}")
    
    if order.city:
        lines.append(f"Localisation: {order.city}")
    
    return "\n".join(lines)

# Template helper functions for Jinja2
def register_template_helpers(app):
    """Register helper functions as Jinja2 template globals
    
    Args:
        app: Flask application instance
    """
    app.jinja_env.globals.update({
        'format_date_french': format_date_french,
        'format_datetime_french': format_datetime_french,
        'format_currency': format_currency,
        'truncate_text': truncate_text,
        'get_condition_class': get_condition_class,
        'get_short_condition': get_short_condition,
        'get_status_info': get_status_info,
        'calculate_time_remaining': calculate_time_remaining,
        'paris_now': paris_now,
        'utc_to_paris': utc_to_paris
    })