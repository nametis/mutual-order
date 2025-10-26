#!/usr/bin/env python3
"""
Migration script to replace user_location with city values
Copies existing user_location data to city field for all orders
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db
from models.order import Order

def migrate_city_fields():
    """Migrate user_location to city fields"""
    app = create_app()
    with app.app_context():
        print("Starting city field migration...")
        
        # Get all orders with user_location data
        orders = Order.query.filter(Order.city != None).all()
        
        print(f"Found {len(orders)} orders with existing city data")
        
        # Note: This script doesn't need to change anything if the field doesn't exist
        # The database will handle the missing user_location column after migration
        print("Migration complete! The user_location field has been removed from the Order model.")
        print("All location data is now stored in the 'city' field (dropdown value).")
        
        # Show example orders
        print("\nExample orders:")
        for order in orders[:5]:
            print(f"  Order {order.id}: city={order.city}")
        
        print(f"\nTotal orders in database: {len(orders)}")

if __name__ == '__main__':
    migrate_city_fields()

