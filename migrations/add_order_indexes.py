#!/usr/bin/env python3
"""
Migration script to add database indexes for Order model optimization
Run this script to add the new indexes to improve query performance
"""

from app import create_app
from models import db

def add_order_indexes():
    """Add optimization indexes to the Order table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Add the new indexes
            db.engine.execute("""
                CREATE INDEX IF NOT EXISTS idx_creator_status 
                ON "order" (creator_id, status);
            """)
            
            db.engine.execute("""
                CREATE INDEX IF NOT EXISTS idx_status_created 
                ON "order" (status, created_at);
            """)
            
            db.engine.execute("""
                CREATE INDEX IF NOT EXISTS idx_creator_created 
                ON "order" (creator_id, created_at);
            """)
            
            # Add index on created_at if it doesn't exist
            db.engine.execute("""
                CREATE INDEX IF NOT EXISTS idx_order_created_at 
                ON "order" (created_at);
            """)
            
            print("✅ Successfully added Order table indexes")
            print("   - idx_creator_status (creator_id, status)")
            print("   - idx_status_created (status, created_at)")
            print("   - idx_creator_created (creator_id, created_at)")
            print("   - idx_order_created_at (created_at)")
            
        except Exception as e:
            print(f"❌ Error adding indexes: {e}")
            return False
            
    return True

if __name__ == "__main__":
    add_order_indexes()
