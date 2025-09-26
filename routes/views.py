from flask import Blueprint, request, redirect, render_template, url_for, flash, current_app
from datetime import datetime
from models import db, Order, Listing
from services import auth_service, discogs_service

views_bp = Blueprint('views', __name__)

def login_required(f):
    """Decorator to require authentication for routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_service.is_authenticated():
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@views_bp.route('/')
@login_required
def index():
    """Main dashboard page"""
    current_user = auth_service.get_current_user()
    return render_template('dashboard.html', current_user=current_user)

@views_bp.route('/order/<int:order_id>')
@login_required
def view_order(order_id):
    """View specific order details"""
    order = Order.query.get_or_404(order_id)
    order_dict = order.to_dict()
    current_user = auth_service.get_current_user()
    
    return render_template('order_v2.html', order=order_dict, current_user=current_user)

@views_bp.route('/create_order_form', methods=['GET', 'POST'])
@login_required
def create_order_form():
    """Create new order form"""
    if request.method == 'POST':
        first_listing_url = request.form.get('first_listing_url', '').strip()
        max_amount = request.form.get('max_amount', type=float)
        max_amount = float(max_amount) if max_amount and max_amount.strip() else None
        deadline_str = request.form.get('deadline', '').strip()
        payment_timing = request.form.get('payment_timing', 'avant la commande')
        seller_shop_url = request.form.get('seller_shop_url', '').strip()
        user_location = request.form.get('user_location', '').strip()
        
        # Debug logging
        current_app.logger.info(f"=== CREATE ORDER DEBUG ===")
        current_app.logger.info(f"URL received: {repr(first_listing_url)}")
        current_app.logger.info(f"URL length: {len(first_listing_url) if first_listing_url else 0}")
        current_app.logger.info(f"Max amount: {max_amount}")
        
        # Validation
        if not first_listing_url:
            current_app.logger.warning("Validation failed: missing required fields")
            flash('Veuillez remplir tous les champs obligatoires.', 'danger')
            return render_template('create_order_form.html')

        if not deadline_str:
            current_app.logger.warning("Validation failed: missing deadline")
            flash('La date limite est obligatoire.', 'danger')
            return render_template('create_order_form.html')
        
        # Parse deadline
        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
                current_app.logger.info(f"Deadline parsed: {deadline}")
            except ValueError:
                current_app.logger.error(f"Invalid date format: {deadline_str}")
                flash('Format de date invalide.', 'danger')
                return render_template('create_order_form.html')
        
        current_user = auth_service.get_current_user()
        current_app.logger.info(f"Current user: {current_user.username if current_user else 'None'}")
        
        try:
            # Extract listing ID using service
            current_app.logger.info("Attempting to extract listing ID...")
            listing_id = discogs_service.extract_listing_id(first_listing_url)
            current_app.logger.info(f"Extracted listing ID: {repr(listing_id)}")
            
            if not listing_id:
                current_app.logger.error(f"Failed to extract listing ID from URL: {first_listing_url}")
                flash('URL Discogs invalide.', 'danger')
                return render_template('create_order_form.html')
            
            current_app.logger.info("Fetching listing data from Discogs API...")
            # Fetch listing data from Discogs
            listing_data = discogs_service.fetch_listing_data(listing_id)
            current_app.logger.info(f"Listing data received: title='{listing_data.get('title', 'N/A')}', seller='{listing_data.get('seller_name', 'N/A')}'")
            
            # Check if order already exists for this seller
            existing_order = Order.query.filter_by(seller_name=listing_data['seller_name']).first()
            if existing_order:
                current_app.logger.info(f"Existing order found for seller {listing_data['seller_name']}")
                flash(f'Une commande existe déjà pour le vendeur {listing_data["seller_name"]}.', 'info')
                return redirect(url_for('views.view_order', order_id=existing_order.id))
            
            current_app.logger.info("Creating new order...")

            paypal_link = request.form.get('paypal_link', '').strip()

            # Create new order
            order = Order(
                seller_name=listing_data['seller_name'],
                creator_id=current_user.id,
                max_amount=max_amount if max_amount else None,
                deadline=deadline,
                payment_timing=payment_timing,
                seller_shop_url=seller_shop_url if seller_shop_url else None,
                user_location=user_location if user_location else None,
                paypal_link=paypal_link if paypal_link else None
            )
            db.session.add(order)
            db.session.flush()  # Get the order ID
            current_app.logger.info(f"Order created with ID: {order.id}")
            
            current_app.logger.info("Creating first listing...")
            # Create first listing
            listing = Listing(
                discogs_id=listing_data['id'],
                title=listing_data['title'],
                price_value=listing_data['price_value'],
                currency=listing_data['currency'],
                media_condition=listing_data['media_condition'],
                sleeve_condition=listing_data['sleeve_condition'],
                image_url=listing_data['image_url'],
                listing_url=first_listing_url,
                status=listing_data['status'],
                user_id=current_user.id,
                order_id=order.id
            )
            db.session.add(listing)
            db.session.commit()
            current_app.logger.info("Order and listing committed to database successfully")
            
            flash(f'Commande créée pour {listing_data["seller_name"]} !', 'success')
            return redirect(url_for('views.view_order', order_id=order.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error creating order: {str(e)}')
            current_app.logger.error(f'Exception type: {type(e).__name__}')
            import traceback
            current_app.logger.error(f'Traceback: {traceback.format_exc()}')
            flash(f'Erreur lors de la création: {str(e)}', 'danger')
            return render_template('create_order_form.html')
    
    return render_template('create_order_form.html')

@views_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    user = auth_service.get_current_user()
    
    # Get user statistics
    user_stats = {
        'orders_created': Order.query.filter_by(creator_id=user.id).count(),
        'orders_participated': Order.query.join(Listing).filter(Listing.user_id == user.id).distinct().count(),
        'total_listings': Listing.query.filter_by(user_id=user.id).count(),
        'active_listings': Listing.query.filter_by(user_id=user.id, status='For Sale').count()
    }
    
    return render_template('profile.html', user=user, stats=user_stats)

@views_bp.route('/orders')
@login_required
def orders_list():
    """List all orders (alternative view to dashboard)"""
    user = auth_service.get_current_user()
    
    # Get filter parameters
    status_filter = request.args.get('status')
    seller_filter = request.args.get('seller')
    my_orders_only = request.args.get('my_orders', type=bool)
    
    # Build query
    query = Order.query
    
    if status_filter:
        query = query.filter(Order.status == status_filter)
    
    if seller_filter:
        query = query.filter(Order.seller_name.ilike(f'%{seller_filter}%'))
    
    if my_orders_only:
        # Either created by user or user has listings in the order
        query = query.filter(
            db.or_(
                Order.creator_id == user.id,
                Order.id.in_(
                    db.session.query(Listing.order_id).filter(Listing.user_id == user.id).distinct()
                )
            )
        )
    
    orders = query.order_by(Order.created_at.desc()).all()
    
    return render_template('orders_list.html', orders=orders, user=user)

@views_bp.route('/help')
def help_page():
    """Help/FAQ page"""
    return render_template('help.html')

@views_bp.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@views_bp.route('/logout')
def logout():
    """Logout user - backup route"""
    auth_service.logout_user()
    flash('Déconnexion réussie.', 'info')
    return redirect(url_for('auth.login'))

# Debug/Admin routes (should be removed in production)
@views_bp.route('/reset_db_with_test_users_and_chat')
@login_required
def reset_db_with_test_users_and_chat():
    """Reset database (admin only)"""
    current_user = auth_service.get_current_user()
    if not current_user.is_admin:
        flash('Accès administrateur requis', 'danger')
        return redirect(url_for('views.index'))
    
    try:
        # Drop all tables and recreate
        db.drop_all()
        db.create_all()
        
        flash('Base de données réinitialisée avec succès ! Connectez-vous avec Discogs pour créer votre compte.', 'success')
        auth_service.logout_user()
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la réinitialisation: {str(e)}', 'danger')
        return redirect(url_for('views.index'))

@views_bp.route('/clear_cache')
@login_required
def clear_cache():
    """Clear all cache (admin only)"""
    current_user = auth_service.get_current_user()
    if not current_user.is_admin:
        flash('Accès administrateur requis', 'danger')
        return redirect(url_for('views.index'))
    
    from services import cache_service
    if cache_service.flush_all():
        flash('Cache vidé avec succès', 'success')
    else:
        flash('Pas de cache Redis disponible', 'info')
    
    return redirect(url_for('views.index'))

@views_bp.route('/settings')
@login_required
def settings():
    """User settings page"""
    user = auth_service.get_current_user()
    return render_template('settings.html', current_user=user)