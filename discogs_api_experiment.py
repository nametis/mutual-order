#!/usr/bin/env python3
"""
Discogs API Experiment Script
Copy this into a Jupyter notebook to experiment with Discogs API requests
"""

import requests
import json
import time
from requests_oauthlib import OAuth1Session

# Configuration - Replace with your actual credentials
DISCOGS_CONSUMER_KEY = "YOUR_CONSUMER_KEY"
DISCOGS_CONSUMER_SECRET = "YOUR_CONSUMER_SECRET"
DISCOGS_ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
DISCOGS_ACCESS_SECRET = "YOUR_ACCESS_SECRET"

# Seller to test with
SELLER_NAME = "FactoryUdine"

def create_oauth_session():
    """Create OAuth session for authenticated requests"""
    return OAuth1Session(
        DISCOGS_CONSUMER_KEY,
        client_secret=DISCOGS_CONSUMER_SECRET,
        resource_owner_key=DISCOGS_ACCESS_TOKEN,
        resource_owner_secret=DISCOGS_ACCESS_SECRET
    )

def make_discogs_request(oauth, page=1, per_page=100, show_raw=False):
    """Make a raw Discogs API request"""
    url = f'https://api.discogs.com/users/{SELLER_NAME}/inventory'
    params = {'page': page, 'per_page': per_page}
    
    print(f"🔍 Making request:")
    print(f"   URL: {url}")
    print(f"   Params: {params}")
    print(f"   Full URL: {url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}")
    print()
    
    try:
        response = oauth.get(url, params=params)
        
        print(f"📊 Response:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            pagination = data.get('pagination', {})
            listings = data.get('listings', [])
            
            print(f"✅ Success!")
            print(f"   Total Items: {pagination.get('items', 0)}")
            print(f"   Total Pages: {pagination.get('pages', 0)}")
            print(f"   Current Page: {pagination.get('page', 0)}")
            print(f"   Items per Page: {pagination.get('per_page', 0)}")
            print(f"   Items in Response: {len(listings)}")
            print()
            
            if show_raw:
                print(f"📄 Raw Response (first 500 chars):")
                print(json.dumps(data, indent=2)[:500] + "...")
                print()
            
            return data, response.status_code
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return None, response.status_code
            
    except Exception as e:
        print(f"💥 Exception: {e}")
        return None, None

def experiment_pagination():
    """Experiment with different pagination approaches"""
    oauth = create_oauth_session()
    
    print("=" * 60)
    print("🧪 DISCOGS API PAGINATION EXPERIMENT")
    print("=" * 60)
    print()
    
    # First, get pagination info
    print("1️⃣ Getting pagination info...")
    data, status = make_discogs_request(oauth, page=1, per_page=100)
    
    if not data:
        print("❌ Failed to get pagination info")
        return
    
    pagination = data.get('pagination', {})
    total_items = pagination.get('items', 0)
    total_pages = pagination.get('pages', 0)
    
    print(f"📈 Summary:")
    print(f"   Total Items: {total_items}")
    print(f"   Total Pages: {total_pages}")
    print()
    
    # Test different pages
    pages_to_test = [1, total_pages - 1, total_pages, total_pages + 1]
    
    for page in pages_to_test:
        if page <= 0:
            continue
            
        print(f"2️⃣ Testing page {page}...")
        data, status = make_discogs_request(oauth, page=page, per_page=100)
        
        if status == 403:
            print(f"   ⚠️  Page {page} returns 403 - page doesn't exist")
        elif status == 200:
            listings = data.get('listings', [])
            print(f"   ✅ Page {page} has {len(listings)} items")
        
        print()
        time.sleep(1)  # Rate limiting
    
    # Test different per_page values
    print("3️⃣ Testing different per_page values...")
    per_page_values = [50, 100, 200, 500]
    
    for per_page in per_page_values:
        print(f"   Testing per_page={per_page} on last page...")
        data, status = make_discogs_request(oauth, page=total_pages, per_page=per_page)
        
        if status == 200:
            listings = data.get('listings', [])
            print(f"   ✅ Got {len(listings)} items with per_page={per_page}")
        else:
            print(f"   ❌ Failed with per_page={per_page}: {status}")
        
        print()
        time.sleep(1)  # Rate limiting

def test_missing_items_scenario():
    """Test the specific scenario of finding missing items"""
    oauth = create_oauth_session()
    
    print("=" * 60)
    print("🔍 MISSING ITEMS SCENARIO TEST")
    print("=" * 60)
    print()
    
    # Simulate having 10,000 cached items from 100 pages
    cached_items = 10000
    cached_pages = 100
    
    print(f"📊 Scenario:")
    print(f"   Cached Items: {cached_items}")
    print(f"   Cached Pages: {cached_pages}")
    print()
    
    # Get current total
    print("1️⃣ Getting current total...")
    data, status = make_discogs_request(oauth, page=1, per_page=100)
    
    if not data:
        return
    
    pagination = data.get('pagination', {})
    total_items = pagination.get('items', 0)
    total_pages = pagination.get('pages', 0)
    missing_count = total_items - cached_items
    
    print(f"   Total Items: {total_items}")
    print(f"   Total Pages: {total_pages}")
    print(f"   Missing Items: {missing_count}")
    print()
    
    # Try to find missing items
    print("2️⃣ Looking for missing items...")
    
    # Try last few pages
    pages_to_check = [total_pages - 2, total_pages - 1, total_pages]
    
    for page in pages_to_check:
        if page <= 0:
            continue
            
        print(f"   Checking page {page}...")
        data, status = make_discogs_request(oauth, page=page, per_page=100)
        
        if status == 200:
            listings = data.get('listings', [])
            print(f"   ✅ Page {page}: {len(listings)} items")
            
            # Show first few item IDs
            if listings:
                item_ids = [str(item.get('id', 'N/A')) for item in listings[:5]]
                print(f"      Sample IDs: {item_ids}")
        elif status == 403:
            print(f"   ⚠️  Page {page}: 403 (doesn't exist)")
        else:
            print(f"   ❌ Page {page}: {status}")
        
        print()
        time.sleep(1)  # Rate limiting

def test_raw_requests():
    """Test raw requests without OAuth to see what happens"""
    print("=" * 60)
    print("🌐 RAW REQUESTS TEST (No OAuth)")
    print("=" * 60)
    print()
    
    # Test without OAuth
    url = f'https://api.discogs.com/users/{SELLER_NAME}/inventory'
    
    print("1️⃣ Testing without OAuth...")
    response = requests.get(url, params={'page': 1, 'per_page': 100})
    print(f"   Status: {response.status_code}")
    print(f"   Headers: {dict(response.headers)}")
    print()
    
    # Test with different User-Agent
    print("2️⃣ Testing with custom User-Agent...")
    headers = {'User-Agent': 'MutualOrder/1.0'}
    response = requests.get(url, params={'page': 1, 'per_page': 100}, headers=headers)
    print(f"   Status: {response.status_code}")
    print(f"   Headers: {dict(response.headers)}")
    print()

# Main execution
if __name__ == "__main__":
    print("🚀 Discogs API Experiment Script")
    print("=" * 60)
    print()
    print("Available functions:")
    print("1. experiment_pagination() - Test different pages and per_page values")
    print("2. test_missing_items_scenario() - Test the missing items scenario")
    print("3. test_raw_requests() - Test raw requests without OAuth")
    print()
    print("To run an experiment, call one of the functions above.")
    print("Example: experiment_pagination()")
    print()
    
    # Uncomment one of these to run the experiment:
    # experiment_pagination()
    # test_missing_items_scenario()
    # test_raw_requests()
