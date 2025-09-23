#!/usr/bin/env python3
"""
Simple test of URL extraction without full app context
"""
import re

def extract_listing_id_simple(url):
    """Simple version of extract_listing_id"""
    if not url:
        return None
    match = re.search(r"/sell/item/(\d+)", url)
    return match.group(1) if match else None

def test_urls():
    """Test with common URLs"""
    test_cases = [
        "https://www.discogs.com/sell/release/14021476",
        "not-a-discogs-url",
        "",
        None
    ]
    
    print("🧪 Simple URL Extraction Test")
    print("=" * 40)
    
    for i, url in enumerate(test_cases, 1):
        result = extract_listing_id_simple(url)
        print(f"{i}. URL: {repr(url)}")
        print(f"   Result: {result}")
        print()

if __name__ == "__main__":
    test_urls()
    
    # Ask user to test their URL
    print("Enter your Discogs URL to test:")
    user_url = input().strip()
    if user_url:
        result = extract_listing_id_simple(user_url)
        print(f"\nYour URL: {user_url}")
        print(f"Extracted ID: {result}")
    else:
        print("No URL provided.")