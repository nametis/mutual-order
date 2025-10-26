import qrcode
import io
import secrets
from datetime import datetime, timezone, timedelta
from models import db, TelegramLinkToken

class QRService:
    """Service for generating QR codes and managing linking tokens"""
    
    @staticmethod
    def generate_linking_token(user_id):
        """Generate a one-time linking token for a user"""
        from models import TelegramLinkToken
        
        # Generate secure random token
        token = secrets.token_urlsafe(32)
        
        # Create token record (no expiry, just single use)
        link_token = TelegramLinkToken(
            user_id=user_id,
            token=token,
            expires_at=None  # No time limit
        )
        
        db.session.add(link_token)
        db.session.commit()
        
        return token
    
    @staticmethod
    def verify_token(token):
        """Verify and consume a linking token"""
        from models import TelegramLinkToken
        
        link_token = TelegramLinkToken.query.filter_by(
            token=token,
            used=False
        ).first()
        
        if not link_token:
            return None
        
        # Check expiry only if it's set
        if link_token.expires_at and link_token.expires_at < datetime.now(timezone.utc):
            return None
        
        # Mark as used
        link_token.used = True
        db.session.commit()
        
        return link_token.user_id
    
    @staticmethod
    def generate_qr_code(data):
        """Generate a QR code image from data"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return img_byte_arr.getvalue()

qr_service = QRService()
