#!/usr/bin/env python3
"""
Quick test to verify imports work without Flask app context
"""

print("Testing imports...")

try:
    print("1. Testing config...")
    from config import config
    print("✅ Config imported")
    
    print("2. Testing models...")
    from models import db, User, Order, Listing, OrderChat, ChatReadStatus
    print("✅ Models imported")
    
    print("3. Testing services...")
    from services import cache_service, discogs_service, auth_service
    print("✅ Services imported")
    
    print("4. Testing routes...")
    from routes import register_blueprints
    print("✅ Routes imported")
    
    print("5. Testing utils...")
    from utils import helpers, decorators
    print("✅ Utils imported")
    
    print("6. Testing main app...")
    from app import create_app, get_app
    print("✅ App imported")
    
    print("\n🎉 All imports successful!")
    print("The import error should be fixed.")
    
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()