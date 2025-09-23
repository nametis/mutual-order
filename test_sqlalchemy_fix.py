#!/usr/bin/env python3
"""
Test the SQLAlchemy fixes for Order model
"""

def test_order_properties():
    try:
        from app import get_app
        app = get_app()
        
        with app.app_context():
            from models import db, Order, User, Listing
            
            print("🧪 Testing Order Model Properties")
            print("=" * 40)
            
            # Get an order to test
            orders = Order.query.all()
            if not orders:
                print("❌ No orders found to test")
                return
            
            test_order = orders[-1]  # Get the latest order
            print(f"📋 Testing order ID: {test_order.id}")
            print(f"   Seller: {test_order.seller_name}")
            
            # Test each property that was fixed
            try:
                total_price = test_order.total_price
                print(f"✅ total_price: {total_price}")
            except Exception as e:
                print(f"❌ total_price failed: {e}")
            
            try:
                currency = test_order.currency
                print(f"✅ currency: {currency}")
            except Exception as e:
                print(f"❌ currency failed: {e}")
            
            try:
                participants_count = test_order.participants_count
                print(f"✅ participants_count: {participants_count}")
            except Exception as e:
                print(f"❌ participants_count failed: {e}")
            
            try:
                participants = test_order.participants
                print(f"✅ participants: {len(participants)} users")
                for p in participants:
                    print(f"   - {p.username}")
            except Exception as e:
                print(f"❌ participants failed: {e}")
            
            # Test user summary
            try:
                if participants:
                    user_summary = test_order.get_user_summary(participants[0].id)
                    print(f"✅ get_user_summary: {user_summary['listings_count']} listings")
                else:
                    print("⏭️  Skipping user summary (no participants)")
            except Exception as e:
                print(f"❌ get_user_summary failed: {e}")
            
            # Test to_dict
            try:
                order_dict = test_order.to_dict(include_listings=True, current_user_id=participants[0].id if participants else None)
                print(f"✅ to_dict: Success (keys: {len(order_dict)})")
            except Exception as e:
                print(f"❌ to_dict failed: {e}")
            
            print(f"\n🎉 Order model testing completed!")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_order_properties()