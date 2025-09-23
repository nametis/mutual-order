from flask import Flask, request, redirect, render_template, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import discogs_client
import re
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', "dev_key_change_in_production")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mutual_order.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

# Make datetime and timezone functions available in templates
app.jinja_env.globals.update(
    datetime=datetime, 
    now=paris_now,
    utc_to_paris=utc_to_paris
)

db = SQLAlchemy(app)

# Configure Discogs client
USER_AGENT = "MutualOrder/1.0"
CONSUMER_KEY = os.getenv('DISCOGS_CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('DISCOGS_CONSUMER_SECRET')
ACCESS_TOKEN = os.getenv('DISCOGS_ACCESS_TOKEN')
ACCESS_SECRET = os.getenv('DISCOGS_ACCESS_SECRET')

if all([CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
    discogsclient = discogs_client.Client(USER_AGENT)
    discogsclient.set_consumer_key(CONSUMER_KEY, CONSUMER_SECRET)
    discogsclient.set_token(ACCESS_TOKEN, ACCESS_SECRET)
    print("✅ Discogs client initialized")
else:
    print("⚠️ Discogs credentials missing")
    exit(1)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<User {self.username}>'

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_name = db.Column(db.String(100), nullable=False, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Order workflow fields
    status = db.Column(db.String(20), default='building', index=True)  # building, validation, ordered, delivered, closed
    status_changed_at = db.Column(db.DateTime, nullable=True)
    validated_by_creator = db.Column(db.Boolean, default=False)
    
    # Order management fields
    max_amount = db.Column(db.Float, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    payment_timing = db.Column(db.String(50), default="avant la commande")
    seller_shop_url = db.Column(db.Text, nullable=True)
    direct_url = db.Column(db.Text, nullable=True)  # New field for direct order URL
    user_location = db.Column(db.String(200), nullable=True)  # Creator location
    shipping_cost = db.Column(db.Float, default=0.0)
    taxes = db.Column(db.Float, default=0.0)
    
    creator = db.relationship('User', backref='created_orders')
    listings = db.relationship('Listing', backref='order', cascade='all, delete-orphan', lazy='dynamic')
    validations = db.relationship('UserValidation', backref='order', cascade='all, delete-orphan')
    
    @property
    def total_price(self):
        return sum(l.price_value for l in self.listings.filter_by(status='For Sale'))
    
    @property
    def contributed_amount(self):
        """Calculate contributed amount from actual added discs"""
        return self.total_price
    
    @property
    def contributed_percentage(self):
        """Calculate contributed percentage from actual added discs"""
        if self.max_amount and self.max_amount > 0:
            return (self.contributed_amount / self.max_amount) * 100
        return 0.0
    
    @property
    def total_with_fees(self):
        return self.total_price + self.shipping_cost + self.taxes
    
    @property
    def currency(self):
        available = self.listings.filter_by(status='For Sale').first()
        return available.currency if available else "EUR"
    
    @property
    def participants(self):
        """Get all unique users who have listings in this order"""
        participant_ids = db.session.query(Listing.user_id.distinct()).filter_by(order_id=self.id).all()
        participant_ids = [pid[0] for pid in participant_ids]
        return User.query.filter(User.id.in_(participant_ids)).all()
    
    @property
    def participants_count(self):
        """Get count of unique participants"""
        return db.session.query(Listing.user_id.distinct()).filter_by(order_id=self.id).count()
    
    @property
    def all_participants_validated(self):
        """Check if all participants have validated"""
        participants = self.participants
        validated_users = [v.user_id for v in self.validations if v.validated]
        return len(participants) > 0 and all(p.id in validated_users for p in participants)

    def __repr__(self):
        return f'<Order {self.id}: {self.seller_name}>'

class UserValidation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    validated = db.Column(db.Boolean, default=False)
    validated_at = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship('User', backref='validations')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'order_id', name='unique_user_order_validation'),
    )

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    discogs_id = db.Column(db.String(20), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    price_value = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(5), nullable=False)
    media_condition = db.Column(db.String(50), nullable=False)
    sleeve_condition = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.Text)
    listing_url = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='For Sale', index=True)
    last_checked = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    
    user = db.relationship('User', backref='user_listings')
    
    __table_args__ = (
        db.UniqueConstraint('discogs_id', 'order_id', name='unique_listing_per_order'),
        db.Index('idx_order_status', 'order_id', 'status'),
        db.Index('idx_user_order', 'user_id', 'order_id'),
    )

    def __repr__(self):
        return f'<Listing {self.discogs_id}: {self.title[:50]}>'

class OrderChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref='chat_messages')
    order = db.relationship('Order', backref='chat_messages')
    
    def __repr__(self):
        return f'<OrderChat {self.id}: {self.message[:50]}>'

class ChatReadStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    last_read_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User')
    order = db.relationship('Order')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'order_id', name='unique_user_order_read_status'),
    )

# Helper functions
def extract_listing_id(url):
    """Extract listing ID from Discogs URL"""
    match = re.search(r"/sell/item/(\d+)", url)
    return match.group(1) if match else None

def fetch_seller_info(seller_name):
    """Fetch seller information from Discogs API"""
    try:
        seller = discogsclient.user(seller_name)
        
        profile_info = {
            'username': seller_name,
            'location': 'Non spécifiée',
            'rating': None,
            'rating_count': 0,
            'num_for_sale': 0,
            'num_collection': 0,
            'total_sold': 0
        }
        
        # Get location
        try:
            location = getattr(seller, 'location', None)
            if location and location.strip():
                profile_info['location'] = location
        except:
            pass
            
        # Get rating_avg
        try:
            rating_avg = getattr(seller, 'rating_avg', None)
            if rating_avg:
                profile_info['rating'] = rating_avg
                print(f"Found rating_avg for {seller_name}: {rating_avg}")
        except:
            pass
            
        # Get number of items for sale
        try:
            for attr in ['num_for_sale', 'inventory_count', 'num_listing']:
                if hasattr(seller, attr):
                    count_val = getattr(seller, attr)
                    if count_val:
                        profile_info['num_for_sale'] = count_val
                        print(f"Found {attr} for {seller_name}: {count_val}")
                        break
        except:
            pass
            
        # Get collection size
        try:
            num_collection = getattr(seller, 'num_collection', None)
            if num_collection:
                profile_info['num_collection'] = num_collection
                print(f"Found num_collection for {seller_name}: {num_collection}")
        except:
            pass
            
        # Try to find total sold (this might not be available)
        try:
            for attr in ['total_sold', 'num_sold', 'sales_count', 'orders_completed']:
                if hasattr(seller, attr):
                    sold_val = getattr(seller, attr)
                    if sold_val:
                        profile_info['total_sold'] = sold_val
                        print(f"Found {attr} for {seller_name}: {sold_val}")
                        break
        except:
            pass
            
        # Try to find rating count
        try:
            for attr in ['rating_count', 'num_ratings', 'total_ratings']:
                if hasattr(seller, attr):
                    count_val = getattr(seller, attr)
                    if count_val:
                        profile_info['rating_count'] = count_val
                        break
        except:
            pass
        
        # Debug: print all available attributes
        print(f"=== All attributes for {seller_name} ===")
        attrs = [attr for attr in dir(seller) if not attr.startswith('_')]
        for attr in attrs:
            try:
                value = getattr(seller, attr)
                if not callable(value) and value is not None and str(value).strip():
                    print(f"{attr}: {value}")
            except:
                pass
        
        return profile_info
        
    except Exception as e:
        return {
            'username': seller_name,
            'location': 'Non spécifiée',
            'rating': None,
            'rating_count': 0,
            'num_for_sale': 0,
            'num_collection': 0,
            'total_sold': 0,
            'error': str(e)
        }

def fetch_discogs_listing_data(listing_id):
    """Fetch listing data from Discogs API"""
    try:
        listing = discogsclient.listing(listing_id)
        
        image_url = None
        if listing.release and listing.release.images:
            image_url = listing.release.images[0].get("uri")
        
        seller_name = "Unknown Seller"
        if hasattr(listing, 'seller') and listing.seller:
            seller_name = listing.seller.username
        
        sleeve_condition = getattr(listing, 'sleeve_condition', listing.condition)
        
        return {
            'id': str(listing.id),
            'title': listing.release.title if listing.release else "Unknown",
            'price_value': float(listing.price.value),
            'currency': listing.price.currency,
            'media_condition': listing.condition,
            'sleeve_condition': sleeve_condition,
            'image_url': image_url,
            'seller_name': seller_name,
            'status': listing.status
        }
    except Exception as e:
        raise Exception(f"Erreur lors de la récupération des données Discogs: {e}")

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get_or_404(session['user_id'])
    all_orders = Order.query.order_by(Order.created_at.desc()).all()
    
    orders_with_info = []
    for order in all_orders:
        user_listings_count = Listing.query.filter_by(order_id=order.id, user_id=user.id).count()
        available_count = order.listings.filter_by(status='For Sale').count()
        total_count = order.listings.count()
        participants = order.participants
        participants_count = order.participants_count
        seller_info = fetch_seller_info(order.seller_name)
        
        orders_with_info.append({
            'order': order,
            'is_creator': order.creator_id == user.id,
            'user_listings_count': user_listings_count,
            'is_participant': user_listings_count > 0,
            'available_count': available_count,
            'total_count': total_count,
            'has_unavailable': available_count < total_count,
            'participants': participants,
            'participants_count': participants_count,
            'seller_info': seller_info
        })
    
    return render_template('dashboard.html', user=user, orders_with_info=orders_with_info)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Veuillez remplir tous les champs.', 'danger')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash('Connexion réussie !', 'success')
            return redirect(url_for('index'))
        else:
            flash('Identifiants incorrects.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Veuillez remplir tous les champs.', 'danger')
            return render_template('register.html')
        
        if len(username) < 3:
            flash('Le nom d\'utilisateur doit contenir au moins 3 caractères.', 'danger')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Le mot de passe doit contenir au moins 6 caractères.', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Nom d\'utilisateur déjà pris.', 'danger')
        else:
            try:
                user = User(username=username, password_hash=generate_password_hash(password))
                db.session.add(user)
                db.session.commit()
                session['user_id'] = user.id
                flash('Compte créé avec succès !', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()
                flash('Erreur lors de la création du compte.', 'danger')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Déconnexion réussie.', 'info')
    return redirect(url_for('login'))

@app.route('/create_order_form', methods=['GET', 'POST'])
def create_order_form():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Get form data
        first_listing_url = request.form.get('first_listing_url', '').strip()
        max_amount = request.form.get('max_amount', type=float)
        deadline_str = request.form.get('deadline', '').strip()
        payment_timing = request.form.get('payment_timing', 'avant la commande')
        seller_shop_url = request.form.get('seller_shop_url', '').strip()
        user_location = request.form.get('user_location', '').strip()
        
        # Validate required fields
        if not first_listing_url:
            flash('Veuillez fournir une URL de la première annonce.', 'danger')
            return render_template('create_order_form.html')
        
        if not max_amount or max_amount <= 0:
            flash('Veuillez indiquer un montant maximum valide.', 'danger')
            return render_template('create_order_form.html')
        
        # Parse deadline
        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
            except ValueError:
                flash('Format de date invalide.', 'danger')
                return render_template('create_order_form.html')
        
        # Extract listing ID and validate
        listing_id = extract_listing_id(first_listing_url)
        if not listing_id:
            flash('URL Discogs invalide.', 'danger')
            return render_template('create_order_form.html')
        
        try:
            listing_data = fetch_discogs_listing_data(listing_id)
            
            # Check if order for this seller already exists
            existing_order = Order.query.filter_by(seller_name=listing_data['seller_name']).first()
            if existing_order:
                flash(f'Une commande existe déjà pour le vendeur {listing_data["seller_name"]}.', 'info')
                return redirect(url_for('view_order', order_id=existing_order.id))
            
            # Create new order with all fields
            order = Order(
                seller_name=listing_data['seller_name'],
                creator_id=session['user_id'],
                max_amount=max_amount,
                deadline=deadline,
                payment_timing=payment_timing,
                seller_shop_url=seller_shop_url if seller_shop_url else None,
                user_location=user_location if user_location else None
            )
            db.session.add(order)
            db.session.flush()
            
            # Add first listing
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
                user_id=session['user_id'],
                order_id=order.id
            )
            db.session.add(listing)
            db.session.commit()
            
            flash(f'Commande créée pour {listing_data["seller_name"]} !', 'success')
            return redirect(url_for('view_order', order_id=order.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'danger')
            return render_template('create_order_form.html')
    
    return render_template('create_order_form.html')

@app.route('/create_order', methods=['POST'])
def create_order():
    # Redirect to the form instead of direct creation
    return redirect(url_for('create_order_form'))

@app.route('/order/<int:order_id>')
def view_order(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    current_user = User.query.get_or_404(session['user_id'])
    
    available_listings = order.listings.filter_by(status='For Sale').all()
    unavailable_listings = order.listings.filter(Listing.status != 'For Sale').all()
    seller_info = fetch_seller_info(order.seller_name)
    
    # Get removed listings (discs from users who didn't validate)
    removed_listings = []
    if order.status == 'validation':
        # Find participants who haven't validated
        participants = order.participants
        validated_user_ids = [v.user_id for v in order.validations if v.validated]
        non_validated_user_ids = [p.id for p in participants if p.id not in validated_user_ids and p.id != order.creator_id]
        
        # Get their listings (these would be "removed" conceptually)
        if non_validated_user_ids:
            removed_listings = [l for l in available_listings if l.user_id in non_validated_user_ids]
            # For display purposes only - don't actually remove from available_listings yet
    
    return render_template('order.html', 
                         order=order, 
                         current_user=current_user,
                         available_listings=available_listings,
                         unavailable_listings=unavailable_listings,
                         removed_listings=removed_listings,
                         seller_info=seller_info)

@app.route('/order/<int:order_id>/update_settings', methods=['POST'])
def update_order_settings(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    current_user = User.query.get_or_404(session['user_id'])
    
    if order.creator_id != current_user.id and not current_user.is_admin:
        flash('Seul le créateur peut modifier les paramètres de la commande.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    try:
        # Order settings
        direct_url = request.form.get('direct_url', '').strip()
        max_amount = request.form.get('max_amount', type=float)
        deadline_str = request.form.get('deadline', '').strip()
        payment_timing = request.form.get('payment_timing', 'avant la commande')
        
        # Fees
        shipping_cost = request.form.get('shipping_cost', type=float, default=0)
        taxes = request.form.get('taxes', type=float, default=0)
        
        order.direct_url = direct_url if direct_url else None
        order.max_amount = max_amount if max_amount else None
        order.payment_timing = payment_timing
        order.shipping_cost = shipping_cost
        order.taxes = taxes
        
        # Parse deadline
        if deadline_str:
            try:
                order.deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
            except ValueError:
                flash('Format de date invalide.', 'danger')
                return redirect(url_for('view_order', order_id=order_id))
        else:
            order.deadline = None
        
        db.session.commit()
        flash('Paramètres et frais mis à jour avec succès.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return redirect(url_for('view_order', order_id=order_id))

@app.route('/order/<int:order_id>/validate_order', methods=['POST'])
def validate_order(order_id):
    """Creator validates the order and moves it to validation phase"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    current_user = User.query.get_or_404(session['user_id'])
    
    if order.creator_id != current_user.id and not current_user.is_admin:
        flash('Seul le créateur peut valider la commande.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    try:
        order.validated_by_creator = True
        order.status = 'validation'
        order.status_changed_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Commande validée ! Les participants peuvent maintenant confirmer leurs montants.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la validation: {str(e)}', 'danger')
    
    return redirect(url_for('view_order', order_id=order_id))

@app.route('/order/<int:order_id>/user_validate', methods=['POST'])
def user_validate_order(order_id):
    """Individual user validates their participation and amounts"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    current_user = User.query.get_or_404(session['user_id'])
    
    # Check if user is a participant
    participants = order.participants
    if current_user not in participants and not current_user.is_admin:
        flash('Vous n\'êtes pas participant à cette commande.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    try:
        # Find or create validation record
        validation = UserValidation.query.filter_by(user_id=current_user.id, order_id=order_id).first()
        if not validation:
            validation = UserValidation(user_id=current_user.id, order_id=order_id)
            db.session.add(validation)
        
        validation.validated = True
        validation.validated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        flash('Vous avez validé votre participation à cette commande.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la validation: {str(e)}', 'danger')
    
    return redirect(url_for('view_order', order_id=order_id))

@app.route('/order/<int:order_id>/change_status/<new_status>', methods=['POST'])
def change_order_status(order_id, new_status):
    """Change order status (creator or admin only)"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    current_user = User.query.get_or_404(session['user_id'])
    
    if order.creator_id != current_user.id and not current_user.is_admin:
        flash('Seul le créateur peut changer le statut de la commande.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    valid_statuses = ['building', 'validation', 'ordered', 'delivered', 'closed']
    if new_status not in valid_statuses:
        flash('Statut invalide.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    try:
        # If moving from validation to ordered, remove listings from non-validated users
        if order.status == 'validation' and new_status == 'ordered':
            participants = order.participants
            validated_user_ids = [v.user_id for v in order.validations if v.validated]
            # Always include creator as validated
            validated_user_ids.append(order.creator_id)
            
            non_validated_user_ids = [p.id for p in participants if p.id not in validated_user_ids]
            
            if non_validated_user_ids:
                # Remove listings from non-validated users
                listings_to_remove = order.listings.filter(Listing.user_id.in_(non_validated_user_ids)).all()
                removed_count = len(listings_to_remove)
                
                for listing in listings_to_remove:
                    db.session.delete(listing)
                
                # Remove their validation records too
                validations_to_remove = UserValidation.query.filter(
                    UserValidation.order_id == order_id,
                    UserValidation.user_id.in_(non_validated_user_ids)
                ).all()
                for validation in validations_to_remove:
                    db.session.delete(validation)
                
                if removed_count > 0:
                    flash(f'{removed_count} disque(s) retiré(s) de la commande (participants non validés).', 'warning')
        
        order.status = new_status
        order.status_changed_at = datetime.now(timezone.utc)
        db.session.commit()
        
        status_messages = {
            'building': 'Commande remise en construction',
            'validation': 'Commande en phase de validation',
            'ordered': 'Commande passée chez le vendeur',
            'delivered': 'Commande livrée',
            'closed': 'Commande fermée'
        }
        flash(status_messages.get(new_status, f'Statut changé vers {new_status}'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors du changement de statut: {str(e)}', 'danger')
    
    return redirect(url_for('view_order', order_id=order_id))

@app.route('/order/<int:order_id>/add_listing', methods=['POST'])
def add_listing_to_order(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    
    # Only allow adding during building phase
    if order.status != 'building':
        flash('Impossible d\'ajouter des disques après la phase de composition.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    listing_url = request.form.get('listing_url', '').strip()
    
    if not listing_url:
        flash('Veuillez fournir une URL.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    listing_id = extract_listing_id(listing_url)
    
    if not listing_id:
        flash('URL Discogs invalide.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    existing = Listing.query.filter_by(discogs_id=listing_id, order_id=order_id).first()
    if existing:
        flash('Cette annonce est déjà présente dans la commande.', 'warning')
        return redirect(url_for('view_order', order_id=order_id))
    
    try:
        listing_data = fetch_discogs_listing_data(listing_id)
        
        if listing_data['seller_name'] != order.seller_name:
            flash(f'Mauvais vendeur: cette annonce appartient à {listing_data["seller_name"]} mais la commande est pour {order.seller_name}', 'danger')
            return redirect(url_for('view_order', order_id=order_id))
        
        # Check if adding this listing would exceed max_amount
        if order.max_amount:
            current_total = order.total_price + order.shipping_cost + order.taxes
            new_total = current_total + listing_data['price_value']
            if new_total > order.max_amount:
                flash(f'Impossible d\'ajouter ce disque: cela dépasserait le montant maximum autorisé. '
                      f'Total actuel: {current_total:.2f} {order.currency}, '
                      f'Nouveau total: {new_total:.2f} {order.currency}, '
                      f'Maximum: {order.max_amount:.2f} {order.currency}', 'warning')
                return redirect(url_for('view_order', order_id=order_id))
        
        listing = Listing(
            discogs_id=listing_data['id'],
            title=listing_data['title'],
            price_value=listing_data['price_value'],
            currency=listing_data['currency'],
            media_condition=listing_data['media_condition'],
            sleeve_condition=listing_data['sleeve_condition'],
            image_url=listing_data['image_url'],
            listing_url=listing_url,
            status=listing_data['status'],
            user_id=session['user_id'],
            order_id=order_id
        )
        db.session.add(listing)
        db.session.commit()
        
        if listing_data['status'] == 'For Sale':
            flash('Annonce ajoutée avec succès !', 'success')
        else:
            flash(f'Annonce ajoutée mais elle n\'est plus disponible (statut: {listing_data["status"]}).', 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('view_order', order_id=order_id))

@app.route('/order/<int:order_id>/delete')
def delete_order(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    
    if order.creator_id != session['user_id']:
        flash('Vous n\'êtes pas autorisé à supprimer cette commande.', 'danger')
        return redirect(url_for('index'))
    
    try:
        db.session.delete(order)
        db.session.commit()
        flash('Commande supprimée avec succès.', 'info')
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors de la suppression.', 'danger')
    
    return redirect(url_for('index'))

@app.route('/order/<int:order_id>/verify')
def verify_order_availability(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    
    verified_count = 0
    updated_count = 0
    unavailable_count = 0
    
    try:
        for listing in order.listings:
            try:
                listing_data = fetch_discogs_listing_data(listing.discogs_id)
                
                verified_count += 1
                old_status = listing.status
                
                listing.title = listing_data.get('title', listing.title)
                listing.price_value = listing_data.get('price_value', listing.price_value)
                listing.currency = listing_data.get('currency', listing.currency)
                listing.media_condition = listing_data.get('media_condition', listing.media_condition)
                listing.sleeve_condition = listing_data.get('sleeve_condition', listing.sleeve_condition)
                listing.image_url = listing_data.get('image_url', listing.image_url)
                listing.status = listing_data.get('status', 'For Sale')
                listing.last_checked = datetime.now(timezone.utc)
                
                if old_status != listing.status:
                    updated_count += 1
                    if listing.status != 'For Sale':
                        unavailable_count += 1
                        
            except Exception as e:
                if listing.status == 'For Sale':
                    listing.status = 'Not Available'
                    listing.last_checked = datetime.now(timezone.utc)
                    updated_count += 1
                    unavailable_count += 1
        
        db.session.commit()
        
        message = f"Vérification terminée: {verified_count} disques vérifiés"
        if updated_count > 0:
            message += f", {updated_count} mis à jour"
        if unavailable_count > 0:
            message += f", {unavailable_count} non-disponibles"
        
        flash(message, 'success')
        
    except Exception as e:
        flash(f"Erreur lors de la vérification: {e}", 'danger')
        db.session.rollback()
    
    return redirect(url_for('view_order', order_id=order_id))

@app.route('/listing/<int:listing_id>/delete')
def delete_listing(listing_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    listing = Listing.query.get_or_404(listing_id)
    order_id = listing.order_id
    order = Order.query.get_or_404(order_id)
    
    # Only allow deletion during building phase
    if order.status != 'building':
        flash('Impossible de supprimer des disques après la phase de composition.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    if listing.user_id != session['user_id']:
        flash('Vous n\'êtes pas autorisé à supprimer cette annonce.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    try:
        db.session.delete(listing)
        db.session.commit()
        flash('Annonce supprimée avec succès.', 'info')
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors de la suppression.', 'danger')
    
    return redirect(url_for('view_order', order_id=order_id))

# Chat functionality routes
@app.route('/order/<int:order_id>/chat/messages')
def get_chat_messages(order_id):
    """Get chat messages for an order"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = User.query.get_or_404(session['user_id'])
    
    # Check if user has access to this order
    participants = order.participants
    if current_user not in participants and order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    messages = OrderChat.query.filter_by(order_id=order_id).order_by(OrderChat.created_at.asc()).all()
    
    messages_data = []
    for message in messages:
        # Convert UTC to Paris time for display
        paris_time = utc_to_paris(message.created_at)
        messages_data.append({
            'id': message.id,
            'username': message.user.username,
            'content': message.message,
            'timestamp': paris_time.strftime('%d/%m %H:%M'),
            'is_own': message.user_id == current_user.id
        })
    
    return jsonify(messages_data)

@app.route('/order/<int:order_id>/chat/send', methods=['POST'])
def send_chat_message(order_id):
    """Send a chat message"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = User.query.get_or_404(session['user_id'])
    
    # Check if user has access to this order
    participants = order.participants
    if current_user not in participants and order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    message_content = data.get('message', '').strip()
    
    if not message_content:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    if len(message_content) > 500:
        return jsonify({'error': 'Message too long'}), 400
    
    try:
        chat_message = OrderChat(
            order_id=order_id,
            user_id=current_user.id,
            message=message_content
        )
        db.session.add(chat_message)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to send message'}), 500

@app.route('/order/<int:order_id>/chat/unread')
def get_unread_chat_count(order_id):
    """Get unread message count for an order"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = User.query.get_or_404(session['user_id'])
    
    # Check if user has access to this order
    participants = order.participants
    if current_user not in participants and order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get last read timestamp for this user
    read_status = ChatReadStatus.query.filter_by(
        user_id=current_user.id,
        order_id=order_id
    ).first()
    
    if read_status:
        last_read_at = read_status.last_read_at
    else:
        # If no read status exists, consider everything unread
        last_read_at = datetime.min.replace(tzinfo=timezone.utc)
    
    # Count messages newer than last read time
    unread_count = OrderChat.query.filter(
        OrderChat.order_id == order_id,
        OrderChat.created_at > last_read_at,
        OrderChat.user_id != current_user.id  # Don't count own messages as unread
    ).count()
    
    return jsonify({'unread_count': unread_count})

@app.route('/order/<int:order_id>/chat/mark_read', methods=['POST'])
def mark_chat_messages_read(order_id):
    """Mark chat messages as read for current user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    order = Order.query.get_or_404(order_id)
    current_user = User.query.get_or_404(session['user_id'])
    
    # Check if user has access to this order
    participants = order.participants
    if current_user not in participants and order.creator_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Update or create read status
        read_status = ChatReadStatus.query.filter_by(
            user_id=current_user.id,
            order_id=order_id
        ).first()
        
        if read_status:
            read_status.last_read_at = datetime.now(timezone.utc)
        else:
            read_status = ChatReadStatus(
                user_id=current_user.id,
                order_id=order_id,
                last_read_at=datetime.now(timezone.utc)
            )
            db.session.add(read_status)
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to mark messages as read'}), 500

# Database reset route
@app.route('/reset_db_with_test_users_and_chat')
def reset_db_with_test_users_and_chat():
    try:
        # Drop all tables and recreate
        db.drop_all()
        db.create_all()
        
        # Create admin user
        admin_user = User(
            username='admin', 
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin_user)
        
        # Create test users
        test_users = [
            ('user1', 'test123'),
            ('user2', 'test123'),
            ('user3', 'test123')
        ]
        
        for username, password in test_users:
            user = User(
                username=username, 
                password_hash=generate_password_hash(password),
                is_admin=False
            )
            db.session.add(user)
        
        db.session.commit()
        
        flash('Base de données réinitialisée avec succès ! Tables: User, Order, Listing, UserValidation, OrderChat, ChatReadStatus créées. Admin (admin/admin123) et utilisateurs test (user1,user2,user3/test123)', 'success')
        return redirect(url_for('login'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la réinitialisation: {str(e)}', 'danger')
        return redirect(url_for('index'))

# Keep old route for backward compatibility
@app.route('/reset_db_with_test_users')
def reset_db_with_test_users():
    return redirect(url_for('reset_db_with_test_users_and_chat'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    flash('Page non trouvée.', 'danger')
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    flash('Erreur interne du serveur.', 'danger')
    return redirect(url_for('index'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("Database tables created")
    app.run(host="0.0.0.0", port=5000, debug=True)