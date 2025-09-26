#!/usr/bin/env python3
"""
Migration script to add wantlist tables to existing database.
This script should be run on the Raspberry Pi to add the new wantlist functionality.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db

def migrate_database():
    """Add wantlist tables to the database"""
    app = create_app()
    
    with app.app_context():
        print("🔄 Starting wantlist database migration...")
        
        try:
            # Create all tables (this will only create new ones)
            db.create_all()
            print("✅ Database migration completed successfully!")
            print("📋 New tables created:")
            print("  - wantlist_item")
            print("  - wantlist_reference")
            
            # Verify tables exist
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'wantlist_item' in tables and 'wantlist_reference' in tables:
                print("✅ Tables verified successfully!")
            else:
                print("❌ Tables not found - migration may have failed")
                return False
                
            return True
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            return False

if __name__ == '__main__':
    success = migrate_database()
    if success:
        print("\n🎉 Migration completed! You can now use the wantlist functionality.")
    else:
        print("\n💥 Migration failed! Check the error messages above.")
        sys.exit(1)
