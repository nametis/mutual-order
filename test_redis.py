#!/usr/bin/env python3
"""
Test Redis connection with different URLs
"""
import redis
import os

def test_redis_connection(url, name):
    print(f"\n🔍 Testing Redis connection: {name}")
    print(f"URL: {url}")
    
    try:
        client = redis.from_url(url, decode_responses=True)
        client.ping()
        print("✅ Connection successful!")
        
        # Test basic operations
        client.set("test_key", "test_value", ex=10)
        value = client.get("test_key")
        print(f"✅ Test write/read: {value}")
        
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Redis Connection Tests")
    print("=" * 40)
    
    # Test different Redis URLs
    redis_urls = [
        ("Environment REDIS_URL", os.getenv('REDIS_URL', 'NOT_SET')),
        ("Docker service name", "redis://redis:6379/0"),
        ("Localhost", "redis://localhost:6379/0"),
        ("127.0.0.1", "redis://127.0.0.1:6379/0"),
    ]
    
    for name, url in redis_urls:
        if url == 'NOT_SET':
            print(f"\n⚠️  {name}: Not set in environment")
            continue
        test_redis_connection(url, name)
    
    print(f"\n🔍 Environment Variables:")
    for key, value in os.environ.items():
        if 'REDIS' in key:
            print(f"  {key}={value}")