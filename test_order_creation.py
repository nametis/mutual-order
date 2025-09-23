#!/usr/bin/env python3
"""
Test order creation step by step
"""

def test_order_creation():
    try:
        from app import get_app
        app = get_app()
        
        with app.app_context():
            from models import db, User
            from services import discogs_service
            
            print("🧪 Testing Order Creation Components")
            print("=" * 40)
            
            # Test 1: Check if we have users
            users = User.query.all()
            print(f"✅ Found {len(users)} users in database")
            
            if not users:
                print("❌ No users found - create a user first")
                return
            
            test_user = users[0]
            print(f"📋 Using test user: {test_user.username}")
            
            # Test 2: Test URL extraction
            print("\n🔍 Testing URL Extraction:")
            test_url = "https://www.discogs.com/sell/item/1234567890"
            listing_id = discogs_service.extract_listing_id(test_url)
            print(f"   Test URL: {test_url}")
            print(f"   Extracted ID: {listing_id}")
            
            if listing_id != "1234567890":
                print("❌ URL extraction failed!")
                return
            else:
                print("✅ URL extraction working")
            
            # Test 3: Check Discogs service
            print(f"\n🔍 Testing Discogs Service:")
            print(f"   Service initialized: {getattr(discogs_service, '_initialized', False)}")
            print(f"   Client available: {discogs_service.client is not None}")
            
            # Initialize service if needed
            if not getattr(discogs_service, '_initialized', False):
                discogs_service._setup_client()
                print(f"   Service initialized: {discogs_service._initialized}")
            
            # Test 4: Test database write
            print(f"\n🔍 Testing Database Write:")
            from models import Order
            
            # Create test order
            test_order = Order(
                seller_name="test_seller",
                creator_id=test_user.id,
                max_amount=100.0,
                payment_timing="avant la commande"
            )
            
            try:
                db.session.add(test_order)
                db.session.flush()
                order_id = test_order.id
                print(f"✅ Test order created with ID: {order_id}")
                
                # Clean up
                db.session.rollback()
                print("✅ Test order cleaned up")
                
            except Exception as e:
                db.session.rollback()
                print(f"❌ Database write failed: {e}")
                return
            
            print(f"\n🎉 All components working! Order creation should work.")
            print(f"\n💡 If order creation still fails, the issue is likely:")
            print(f"   1. Invalid Discogs URL format")
            print(f"   2. Discogs API credentials not working")
            print(f"   3. Network connectivity to Discogs")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_order_creation()