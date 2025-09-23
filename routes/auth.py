from flask import Blueprint, request, redirect, render_template, url_for, flash, session, jsonify
from services import auth_service
from models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login')
def login():
    """Login page with reconnection option"""
    return render_template('login.html')

@auth_bp.route('/quick_reconnect', methods=['POST'])
def quick_reconnect():
    """Quick reconnect using existing Discogs username"""
    discogs_username = request.form.get('discogs_username', '').strip()
    
    if not discogs_username:
        flash('Veuillez entrer votre nom d\'utilisateur Discogs', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        # Look for existing user
        user = User.query.filter_by(discogs_username=discogs_username).first()
        
        if not user:
            flash('Utilisateur non trouvé. Utilisez la connexion Discogs pour créer votre compte.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not user.profile_completed:
            flash(f'Compte trouvé pour {discogs_username}. Finalisation du profil requise.', 'info')
            auth_service.login_user(user)
            return redirect(url_for('auth.setup_profile'))
        
        # Test if existing tokens are still valid
        if not auth_service.test_user_tokens(user):
            flash('Vos tokens Discogs ont expiré ou sont invalides. Reconnexion via Discogs requise.', 'warning')
            return redirect(url_for('auth.discogs_oauth_start'))
        
        # Login successful
        auth_service.login_user(user)
        flash(f'Reconnexion réussie ! Bienvenue {user.username} 🎉', 'success')
        return redirect(url_for('views.index'))
        
    except Exception as e:
        flash('Erreur lors de la reconnexion. Utilisez la connexion Discogs.', 'danger')
        return redirect(url_for('auth.login'))

@auth_bp.route('/discogs')
def discogs_oauth_start():
    """Start Discogs OAuth process"""
    try:
        authorization_url = auth_service.start_discogs_oauth()
        return redirect(authorization_url)
    except Exception as e:
        flash(f'Erreur OAuth: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))

@auth_bp.route('/discogs/callback')
def discogs_oauth_callback():
    """Discogs OAuth callback"""
    oauth_token = request.args.get('oauth_token')
    oauth_verifier = request.args.get('oauth_verifier')
    
    if not oauth_token or not oauth_verifier:
        flash('Autorisation Discogs annulée', 'warning')
        return redirect(url_for('auth.login'))
    
    try:
        user, is_new_user = auth_service.complete_discogs_oauth(oauth_token, oauth_verifier)
        auth_service.login_user(user)
        
        # Redirect based on profile completion status
        if is_new_user or not user.profile_completed:
            flash(f'Bienvenue {user.discogs_username} ! Choisissez votre pseudo pour Mutual Order.', 'info')
            return redirect(url_for('auth.setup_profile'))
        else:
            flash(f'Reconnecté avec Discogs: {user.discogs_username}', 'success')
            return redirect(url_for('views.index'))
            
    except Exception as e:
        flash(f'Erreur lors de la connexion: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
def logout():
    """Logout user"""
    current_user = auth_service.get_current_user()
    username = current_user.username if current_user else "utilisateur"
    
    auth_service.logout_user()
    flash(f'À bientôt {username} ! Vous êtes déconnecté de Mutual Order.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/setup_profile', methods=['GET', 'POST'])
def setup_profile():
    """Setup user profile after OAuth"""
    if not auth_service.is_authenticated():
        return redirect(url_for('auth.login'))
    
    user = auth_service.get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    
    # If profile is already completed, redirect
    if user.profile_completed:
        return redirect(url_for('views.index'))
    
    if request.method == 'POST':
        mutual_order_username = request.form.get('mutual_order_username', '').strip()
        
        try:
            auth_service.complete_user_profile(user, mutual_order_username)
            flash(f'Profil configuré avec succès ! Bienvenue {mutual_order_username}', 'success')
            return redirect(url_for('views.index'))
        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            flash('Erreur lors de l\'enregistrement', 'danger')
    
    return render_template('setup_profile.html', user=user)

@auth_bp.route('/check_username', methods=['POST'])
def check_username():
    """API to check username availability in real-time"""
    if not auth_service.is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    username = data.get('username', '').strip()
    current_user = auth_service.get_current_user()
    
    available, message = auth_service.check_username_availability(username, current_user.id)
    
    return jsonify({
        'available': available,
        'message': message
    })