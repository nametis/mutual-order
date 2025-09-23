#!/usr/bin/env python3
"""
Debug order creation by testing all components
"""

print("🔍 Debug Order Creation")
print("=" * 30)

# Test 1: Import all required modules
try:
    from app import get_app
    from models import db, Order, Listing, User
    from services import discogs_service, auth_service
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    exit(1)

# Test 2: Create app context and test database
try:
    app = get_app()
    with app.app_context():
        # Test database connection
        users = User.query.limit(1).all()
        print(f"✅ Database connected ({len(users)} users found)")
        
        # Test discogs service
        test_url = "https://www.discogs.com/sell/item/1234567890"
        listing_id = discogs_service.extract_listing_id(test_url)
        if listing_id == "1234567890":
            print("✅ Discogs URL extraction working")
        else:
            print(f"❌ URL extraction failed: got {listing_id}")
        
        # Test service initialization
        if hasattr(discogs_service, '_initialized'):
            if not discogs_service._initialized:
                discogs_service._setup_client()
            print(f"✅ Discogs service initialized: {discogs_service._initialized}")
        
        print("\n🔍 Testing with real Discogs URL (if provided)...")
        print("Enter a test Discogs listing URL (or press Enter to skip):")
        test_url = input().strip()
        
        if test_url and "discogs.com/sell/item" in test_url:
            try:
                listing_id = discogs_service.extract_listing_id(test_url)
                print(f"📋 Extracted listing ID: {listing_id}")
                
                # Only test API call if credentials are configured
                if discogs_service.client:
                    print("🔍 Testing Discogs API call...")
                    listing_data = discogs_service.fetch_listing_data(listing_id)
                    print(f"✅ API call successful!")
                    print(f"   Title: {listing_data.get('title', 'N/A')}")
                    print(f"   Seller: {listing_data.get('seller_name', 'N/A')}")
                    print(f"   Price: {listing_data.get('price_value', 'N/A')} {listing_data.get('currency', '')}")
                else:
                    print("⚠️ Discogs client not configured (credentials missing)")
                    
            except Exception as e:
                print(f"❌ Discogs API test failed: {e}")
        else:
            print("⏭️ Skipping Discogs API test")
            
except Exception as e:
    print(f"❌ App context test failed: {e}")
    import traceback
    traceback.print_exc()
    
print(f"\n🔍 Environment Check:")
import os
required_vars = [
    'DATABASE_URL', 'REDIS_URL', 'SECRET_KEY',
    'DISCOGS_CONSUMER_KEY', 'DISCOGS_CONSUMER_SECRET',
    'DISCOGS_ACCESS_TOKEN', 'DISCOGS_ACCESS_SECRET'
]

for var in required_vars:
    value = os.getenv(var)
    if value:
        # Show first/last few chars for security
        if len(value) > 10:
            display_value = f"{value[:5]}...{value[-3:]}"
        else:
            display_value = "***"
        print(f"  ✅ {var}={display_value}")
    else:
        print(f"  ❌ {var}=NOT SET")

print(f"\n📋 Summary:")
print(f"If order creation fails, check:")
print(f"1. All environment variables are set")
print(f"2. Discogs API credentials are valid")
print(f"3. Database is writable")
print(f"4. Check Flask logs for detailed error messages")