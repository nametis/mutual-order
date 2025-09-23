#!/usr/bin/env python3
"""
Database initialization script for Mutual Order
Creates admin and test users, resets the database
"""

import sys
import os
from werkzeug.security import generate_password_hash

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User

def reset_database():
    """Reset the database and create admin + test users"""
    with app.app_context():
        print("🗑️  Dropping all existing tables...")
        db.drop_all()
        
        print("📋 Creating new tables...")
        db.create_all()
        
        print("👤 Creating admin user...")
        admin_user = User(
            username='admin', 
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin_user)
        print("   ✅ Created admin: admin")
        
        print("👥 Creating test users...")
        test_users = [
            ('user1', 'test123'),
            ('user2', 'test123'),
            ('user3', 'test123')
        ]
        
        for username, password in test_users:
            user = User(
                username=username, 
                password_hash=generate_password_hash(password),
                is_admin=False
            )
            db.session.add(user)
            print(f"   ✅ Created user: {username}")
        
        db.session.commit()
        
        print("\n🎉 Database reset complete!")
        print("\nUsers created:")
        print("   🔧 Admin: admin | Password: admin123")
        for username, password in test_users:
            print(f"   👤 Username: {username} | Password: {password}")
        
        print("\nYou can now run your app with: python app.py")
        print("Or visit: http://localhost:5000/reset_db_with_test_users")

if __name__ == "__main__":
    reset_database()