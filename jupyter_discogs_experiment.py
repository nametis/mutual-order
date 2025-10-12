# Copy this entire cell into a Jupyter notebook
# Discogs API Experiment - Raw Requests

import requests
import json
import time
from requests_oauthlib import OAuth1Session

# =============================================================================
# CONFIGURATION - Replace with your actual credentials
# =============================================================================
DISCOGS_CONSUMER_KEY = "YOUR_CONSUMER_KEY"
DISCOGS_CONSUMER_SECRET = "YOUR_CONSUMER_SECRET" 
DISCOGS_ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
DISCOGS_ACCESS_SECRET = "YOUR_ACCESS_SECRET"
SELLER_NAME = "FactoryUdine"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_oauth_session():
    """Create OAuth session for authenticated requests"""
    return OAuth1Session(
        DISCOGS_CONSUMER_KEY,
        client_secret=DISCOGS_CONSUMER_SECRET,
        resource_owner_key=DISCOGS_ACCESS_TOKEN,
        resource_owner_secret=DISCOGS_ACCESS_SECRET
    )

def make_request(oauth, page=1, per_page=100, show_details=True):
    """Make a Discogs API request and show details"""
    url = f'https://api.discogs.com/users/{SELLER_NAME}/inventory'
    params = {'page': page, 'per_page': per_page}
    
    if show_details:
        print(f"🔍 Request: {url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}")
    
    response = oauth.get(url, params=params)
    
    if show_details:
        print(f"📊 Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        pagination = data.get('pagination', {})
        listings = data.get('listings', [])
        
        if show_details:
            print(f"✅ Items: {len(listings)} | Total: {pagination.get('items', 0)} | Pages: {pagination.get('pages', 0)}")
        
        return data, response.status_code
    else:
        if show_details:
            print(f"❌ Error: {response.status_code} - {response.text[:100]}")
        return None, response.status_code

# =============================================================================
# EXPERIMENT 1: Test Pagination
# =============================================================================

def test_pagination():
    """Test different pages to understand pagination"""
    print("🧪 TESTING PAGINATION")
    print("=" * 50)
    
    oauth = create_oauth_session()
    
    # Get basic info
    data, status = make_request(oauth, page=1, per_page=100)
    if not data:
        return
    
    pagination = data.get('pagination', {})
    total_pages = pagination.get('pages', 0)
    total_items = pagination.get('items', 0)
    
    print(f"\n📈 Total: {total_items} items across {total_pages} pages")
    print()
    
    # Test different pages
    test_pages = [1, total_pages - 1, total_pages, total_pages + 1]
    
    for page in test_pages:
        if page <= 0:
            continue
        print(f"Testing page {page}:")
        data, status = make_request(oauth, page=page, per_page=100)
        time.sleep(1)  # Rate limiting
        print()

# =============================================================================
# EXPERIMENT 2: Missing Items Scenario
# =============================================================================

def test_missing_items():
    """Test the specific missing items scenario"""
    print("🔍 TESTING MISSING ITEMS SCENARIO")
    print("=" * 50)
    
    oauth = create_oauth_session()
    
    # Simulate having 10,000 cached items
    cached_items = 10000
    
    # Get current total
    data, status = make_request(oauth, page=1, per_page=100)
    if not data:
        return
    
    pagination = data.get('pagination', {})
    total_items = pagination.get('items', 0)
    total_pages = pagination.get('pages', 0)
    missing_count = total_items - cached_items
    
    print(f"📊 Scenario:")
    print(f"   Cached: {cached_items} items")
    print(f"   Total: {total_items} items") 
    print(f"   Missing: {missing_count} items")
    print(f"   Total Pages: {total_pages}")
    print()
    
    # Try to find missing items on last pages
    print("🔍 Checking last few pages for missing items:")
    
    for page in [total_pages - 2, total_pages - 1, total_pages]:
        if page <= 0:
            continue
            
        print(f"\nPage {page}:")
        data, status = make_request(oauth, page=page, per_page=100)
        
        if status == 200:
            listings = data.get('listings', [])
            print(f"   Found {len(listings)} items")
            if listings:
                # Show sample item IDs
                sample_ids = [str(item.get('id', 'N/A')) for item in listings[:3]]
                print(f"   Sample IDs: {sample_ids}")
        elif status == 403:
            print(f"   ❌ 403 - Page doesn't exist")
        else:
            print(f"   ❌ Error {status}")
        
        time.sleep(1)  # Rate limiting

# =============================================================================
# EXPERIMENT 3: Different per_page Values
# =============================================================================

def test_per_page_values():
    """Test different per_page values"""
    print("📄 TESTING DIFFERENT per_page VALUES")
    print("=" * 50)
    
    oauth = create_oauth_session()
    
    # Get total pages first
    data, status = make_request(oauth, page=1, per_page=100)
    if not data:
        return
    
    total_pages = data.get('pagination', {}).get('pages', 0)
    last_page = total_pages
    
    print(f"Testing on page {last_page} with different per_page values:")
    print()
    
    per_page_values = [50, 100, 200, 500]
    
    for per_page in per_page_values:
        print(f"per_page={per_page}:")
        data, status = make_request(oauth, page=last_page, per_page=per_page)
        
        if status == 200:
            listings = data.get('listings', [])
            print(f"   ✅ Got {len(listings)} items")
        else:
            print(f"   ❌ Error {status}")
        
        time.sleep(1)  # Rate limiting
        print()

# =============================================================================
# EXPERIMENT 4: Raw Requests (No OAuth)
# =============================================================================

def test_raw_requests():
    """Test raw requests without OAuth"""
    print("🌐 TESTING RAW REQUESTS (No OAuth)")
    print("=" * 50)
    
    url = f'https://api.discogs.com/users/{SELLER_NAME}/inventory'
    
    print("1. Without OAuth:")
    response = requests.get(url, params={'page': 1, 'per_page': 100})
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}...")
    print()
    
    print("2. With User-Agent:")
    headers = {'User-Agent': 'MutualOrder/1.0'}
    response = requests.get(url, params={'page': 1, 'per_page': 100}, headers=headers)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}...")
    print()

# =============================================================================
# RUN EXPERIMENTS
# =============================================================================

print("🚀 Discogs API Experiment Script")
print("=" * 60)
print()
print("Available experiments:")
print("1. test_pagination() - Test different pages")
print("2. test_missing_items() - Test missing items scenario") 
print("3. test_per_page_values() - Test different per_page values")
print("4. test_raw_requests() - Test raw requests")
print()
print("To run an experiment, call one of the functions above.")
print("Example: test_pagination()")
print()

# Uncomment one of these to run:
# test_pagination()
# test_missing_items()
# test_per_page_values()
# test_raw_requests()
