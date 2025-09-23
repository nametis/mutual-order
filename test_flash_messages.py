#!/usr/bin/env python3
"""
Test flash message behavior
"""

def test_flash_messages():
    try:
        from app import get_app
        from flask import session
        
        app = get_app()
        
        with app.test_client() as client:
            with client.session_transaction() as sess:
                print("🧪 Testing Flash Message System")
                print("=" * 40)
                
                # Check if session is working
                print(f"Session keys: {list(sess.keys())}")
                
                # Check for any existing flash messages
                flashes = sess.get('_flashes', [])
                print(f"Existing flash messages: {flashes}")
                
                if flashes:
                    print("⚠️ Found existing flash messages - this might be the issue!")
                    print("Flash messages should be consumed after each request.")
                else:
                    print("✅ No lingering flash messages found")
    
    except Exception as e:
        print(f"❌ Flash message test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_flash_messages()