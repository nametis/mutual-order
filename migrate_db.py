"""
Database migration script to add user settings fields.
Run this script to add the new fields to existing users table.
"""

import sqlite3
import os

def migrate_database():
    """Add new fields to the users table"""
    
    # Get database path
    db_path = 'instance/mutual_order.db'
    
    if not os.path.exists(db_path):
        print("Database not found. Please ensure the database exists.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(user)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add default_location column if it doesn't exist
        if 'default_location' not in columns:
            cursor.execute('ALTER TABLE user ADD COLUMN default_location VARCHAR(200)')
            print("✅ Added default_location column")
        else:
            print("⚠️  default_location column already exists")
        
        # Add default_paypal_link column if it doesn't exist
        if 'default_paypal_link' not in columns:
            cursor.execute('ALTER TABLE user ADD COLUMN default_paypal_link TEXT')
            print("✅ Added default_paypal_link column")
        else:
            print("⚠️  default_paypal_link column already exists")
        
        conn.commit()
        print("✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔄 Starting database migration...")
    migrate_database()
    print("🔄 Migration finished.")