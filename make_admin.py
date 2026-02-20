#!/usr/bin/env python3
"""Helper script to make a user admin by their Telegram ID."""

import sys
from database import init_db, User

def make_admin(telegram_id):
    """Make a user admin by their Telegram ID."""
    db = init_db()()
    
    try:
        # Find user
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        
        if not user:
            print(f"❌ User with Telegram ID {telegram_id} not found in database.")
            print("   The user must interact with the bot first (send /start).")
            return False
        
        if user.is_admin:
            print(f"ℹ️  User {telegram_id} (@{user.username or 'N/A'}) is already an admin.")
            return True
        
        # Make user admin
        user.is_admin = True
        db.commit()
        
        print(f"✅ User {telegram_id} (@{user.username or 'N/A'}) is now an admin!")
        return True
    finally:
        db.close()


def list_users():
    """List all users in the database."""
    db = init_db()()
    
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        
        if not users:
            print("No users found in database.")
            return
        
        print(f"\n{'='*70}")
        print("Users in Database:")
        print(f"{'='*70}")
        
        for user in users:
            admin_badge = "🔑 ADMIN" if user.is_admin else "👤 USER"
            username_str = f"@{user.username}" if user.username else "N/A"
            print(f"{admin_badge} | Telegram ID: {user.telegram_id} | Username: {username_str}")
            print(f"         Joined: {user.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print()
    finally:
        db.close()


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python make_admin.py <telegram_id>     # Make a user admin")
        print("  python make_admin.py --list             # List all users")
        print()
        print("Example:")
        print("  python make_admin.py 123456789")
        sys.exit(1)
    
    if sys.argv[1] == "--list":
        list_users()
    else:
        try:
            telegram_id = int(sys.argv[1])
            make_admin(telegram_id)
        except ValueError:
            print(f"❌ Invalid Telegram ID: {sys.argv[1]}")
            print("   Telegram ID must be a number.")
            sys.exit(1)


if __name__ == '__main__':
    main()
