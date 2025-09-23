from flask import Flask, request, redirect, render_template, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import discogs_client
import re
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', "dev_key_change_in_production")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mutual_order.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<User {self.username}>'

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_name = db.Column(db.String(100), nullable=False, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    creator = db.relationship('User', backref='created_orders')
    listings = db.relationship('Listing', backref='order', cascade='all, delete-orphan', lazy='dynamic')
    
    @property
    def total_price(self):
        return sum(l.price_value for l in self.listings.filter_by(status='For Sale'))
    
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

    def __repr__(self):
        return f'<Order {self.id}: {self.seller_name}>'

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    discogs_id = db.Column(db.String(20), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)  # Increased length for longer titles
    price_value = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(5), nullable=False)
    media_condition = db.Column(db.String(50), nullable=False)
    sleeve_condition = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.Text)  # Changed to TEXT for longer URLs
    listing_url = db.Column(db.Text, nullable=False)  # Changed to TEXT for longer URLs
    status = db.Column(db.String(50), default='For Sale', index=True)
    last_checked = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    
    user = db.relationship('User', backref='user_listings')
    
    # Add unique constraint to prevent duplicate listings in same order
    __table_args__ = (
        db.UniqueConstraint('discogs_id', 'order_id', name='unique_listing_per_order'),
        db.Index('idx_order_status', 'order_id', 'status'),
        db.Index('idx_user_order', 'user_id', 'order_id'),
    )

    def __repr__(self):
        return f'<Listing {self.discogs_id}: {self.title[:50]}>'

# Helper functions
def extract_listing_id(url):
    """Extract listing ID from Discogs URL"""
    match = re.search(r"/sell/item/(\d+)", url)
    return match.group(1) if match else None

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
        
        # Handle missing sleeve condition
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
        # Get user's listings count for this order
        user_listings_count = Listing.query.filter_by(order_id=order.id, user_id=user.id).count()
        
        # Get available and total listings count
        available_count = order.listings.filter_by(status='For Sale').count()
        total_count = order.listings.count()
        
        # Get participants information
        participants = order.participants
        participants_count = order.participants_count
        
        orders_with_info.append({
            'order': order,
            'is_creator': order.creator_id == user.id,
            'user_listings_count': user_listings_count,
            'is_participant': user_listings_count > 0,
            'available_count': available_count,
            'total_count': total_count,
            'has_unavailable': available_count < total_count,
            'participants': participants,
            'participants_count': participants_count
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

@app.route('/create_order', methods=['POST'])
def create_order():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    first_listing_url = request.form.get('first_listing_url', '').strip()
    
    if not first_listing_url:
        flash('Veuillez fournir une URL.', 'danger')
        return redirect(url_for('index'))
    
    listing_id = extract_listing_id(first_listing_url)
    
    if not listing_id:
        flash('URL Discogs invalide. Veuillez utiliser une URL au format: https://www.discogs.com/sell/item/...', 'danger')
        return redirect(url_for('index'))
    
    try:
        listing_data = fetch_discogs_listing_data(listing_id)
        
        # Check if order for this seller already exists
        existing_order = Order.query.filter_by(seller_name=listing_data['seller_name']).first()
        if existing_order:
            flash(f'Une commande existe déjà pour le vendeur {listing_data["seller_name"]}. Rejoignez la commande existante.', 'info')
            return redirect(url_for('view_order', order_id=existing_order.id))
        
        # Create new order
        order = Order(seller_name=listing_data['seller_name'], creator_id=session['user_id'])
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
        return redirect(url_for('index'))

@app.route('/order/<int:order_id>')
def view_order(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    current_user = User.query.get_or_404(session['user_id'])
    
    available_listings = order.listings.filter_by(status='For Sale').all()
    unavailable_listings = order.listings.filter(Listing.status != 'For Sale').all()
    
    return render_template('order.html', 
                         order=order, 
                         current_user=current_user,
                         available_listings=available_listings,
                         unavailable_listings=unavailable_listings)

@app.route('/order/<int:order_id>/add_listing', methods=['POST'])
def add_listing_to_order(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    listing_url = request.form.get('listing_url', '').strip()
    
    if not listing_url:
        flash('Veuillez fournir une URL.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    listing_id = extract_listing_id(listing_url)
    
    if not listing_id:
        flash('URL Discogs invalide.', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    
    # Check if listing already exists in this order
    existing = Listing.query.filter_by(discogs_id=listing_id, order_id=order_id).first()
    if existing:
        flash('Cette annonce est déjà présente dans la commande.', 'warning')
        return redirect(url_for('view_order', order_id=order_id))
    
    try:
        listing_data = fetch_discogs_listing_data(listing_id)
        
        if listing_data['seller_name'] != order.seller_name:
            flash(f'Mauvais vendeur: cette annonce appartient à {listing_data["seller_name"]} mais la commande est pour {order.seller_name}', 'danger')
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
                
                # Update all fields with current data
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
                # Listing couldn't be fetched - mark as unavailable
                if listing.status == 'For Sale':
                    listing.status = 'Not Available'
                    listing.last_checked = datetime.now(timezone.utc)
                    updated_count += 1
                    unavailable_count += 1
        
        db.session.commit()
        
        # Create success message
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