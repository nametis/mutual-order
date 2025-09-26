#!/usr/bin/env python3
"""
Test script for the wantlist functionality.
This script can be run to test the wantlist features without the full web interface.
"""

import os
import sys
import json
from datetime import datetime, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User, WantlistItem, WantlistReference, Listing
from services import wantlist_service

def test_wantlist_functionality():
    """Test the wantlist functionality"""
    app = create_app('testing')
    
    with app.app_context():
        print("🧪 Testing Wantlist Functionality")
        print("=" * 50)
        
        # Create test database
        db.create_all()
        
        # Create a test user
        test_user = User(
            discogs_username='test_user',
            discogs_access_token='test_token',
            discogs_access_secret='test_secret',
            mutual_order_username='test_mutual',
            profile_completed=True
        )
        db.session.add(test_user)
        db.session.commit()
        
        print(f"✅ Created test user: {test_user.username}")
        
        # Test 1: Create sample wantlist items
        print("\n📋 Test 1: Creating sample wantlist items")
        sample_wantlist = [
            {
                'id': '12345',
                'release_id': '67890',
                'title': 'Test Album - Artist Name',
                'artists': ['Artist Name'],
                'year': 2020,
                'format': 'Vinyl, LP',
                'thumb': 'https://example.com/thumb.jpg',
                'date_added': '2024-01-01T00:00:00Z'
            },
            {
                'id': '12346',
                'release_id': '67891',
                'title': 'Another Album - Different Artist',
                'artists': ['Different Artist'],
                'year': 2019,
                'format': 'Vinyl, LP',
                'thumb': 'https://example.com/thumb2.jpg',
                'date_added': '2024-01-02T00:00:00Z'
            }
        ]
        
        for want_data in sample_wantlist:
            wantlist_item = WantlistItem(
                user_id=test_user.id,
                discogs_want_id=str(want_data['id']),
                release_id=str(want_data['release_id']),
                title=want_data['title'],
                artists=json.dumps(want_data['artists']),
                year=want_data['year'],
                format=want_data['format'],
                thumb_url=want_data['thumb'],
                date_added=datetime.fromisoformat(want_data['date_added'].replace('Z', '+00:00'))
            )
            db.session.add(wantlist_item)
        
        db.session.commit()
        print(f"✅ Created {len(sample_wantlist)} wantlist items")
        
        # Test 2: Create sample listings
        print("\n📦 Test 2: Creating sample listings")
        sample_listings = [
            {
                'discogs_id': '11111',
                'title': 'Test Album - Artist Name (2020)',
                'price_value': 25.99,
                'currency': 'EUR',
                'media_condition': 'Near Mint (NM or M-)',
                'sleeve_condition': 'Near Mint (NM or M-)',
                'image_url': 'https://example.com/listing1.jpg',
                'listing_url': 'https://discogs.com/sell/item/11111',
                'status': 'For Sale',
                'user_id': test_user.id,
                'order_id': 1
            },
            {
                'discogs_id': '11112',
                'title': 'Another Album - Different Artist (2019)',
                'price_value': 19.99,
                'currency': 'EUR',
                'media_condition': 'Very Good Plus (VG+)',
                'sleeve_condition': 'Very Good Plus (VG+)',
                'image_url': 'https://example.com/listing2.jpg',
                'listing_url': 'https://discogs.com/sell/item/11112',
                'status': 'For Sale',
                'user_id': test_user.id,
                'order_id': 1
            },
            {
                'discogs_id': '11113',
                'title': 'Unrelated Album - Some Artist (2021)',
                'price_value': 15.99,
                'currency': 'EUR',
                'media_condition': 'Good (G)',
                'sleeve_condition': 'Good (G)',
                'image_url': 'https://example.com/listing3.jpg',
                'listing_url': 'https://discogs.com/sell/item/11113',
                'status': 'For Sale',
                'user_id': test_user.id,
                'order_id': 1
            }
        ]
        
        for listing_data in sample_listings:
            listing = Listing(**listing_data)
            db.session.add(listing)
        
        db.session.commit()
        print(f"✅ Created {len(sample_listings)} sample listings")
        
        # Test 3: Test wantlist service
        print("\n🔍 Test 3: Testing wantlist service")
        
        # Get wantlist
        wantlist = wantlist_service.get_user_wantlist(test_user.id)
        print(f"✅ Retrieved {len(wantlist)} wantlist items")
        
        # Find references
        references = wantlist_service.find_references_in_listings(test_user.id)
        print(f"✅ Found {len(references)} references")
        
        # Get stats
        stats = wantlist_service.get_wantlist_stats(test_user.id)
        print(f"✅ Stats: {stats}")
        
        # Test 4: Test API endpoints (simulate)
        print("\n🌐 Test 4: Testing API endpoints (simulation)")
        
        # Simulate sync endpoint
        try:
            synced_items = wantlist_service.sync_user_wantlist(test_user.id, force_refresh=True)
            print(f"✅ Sync simulation: {len(synced_items)} items")
        except Exception as e:
            print(f"⚠️ Sync simulation failed (expected without real Discogs API): {e}")
        
        # Test 5: Display results
        print("\n📊 Test 5: Results Summary")
        print("-" * 30)
        
        print(f"Wantlist items: {len(wantlist)}")
        for item in wantlist:
            print(f"  - {item['title']} ({item['year']})")
        
        print(f"\nReferences found: {len(references)}")
        for ref in references:
            print(f"  - {ref['wantlist_item']['title']} -> {ref['listing']['title']} (confidence: {ref['match_confidence']:.2f})")
        
        print(f"\nStatistics:")
        for key, value in stats.items():
            print(f"  - {key}: {value}")
        
        # Cleanup
        print("\n🧹 Cleaning up test data...")
        WantlistReference.query.delete()
        WantlistItem.query.delete()
        Listing.query.delete()
        User.query.delete()
        db.session.commit()
        print("✅ Test data cleaned up")
        
        print("\n🎉 All tests completed successfully!")

if __name__ == '__main__':
    test_wantlist_functionality()
