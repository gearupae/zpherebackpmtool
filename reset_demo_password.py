#!/usr/bin/env python3
"""
Reset password for existing demo tenant user
"""
import sys
import os
sys.path.append('/Users/ajaskv/Project/zphere/backend')

from app.core.security import get_password_hash

def main():
    # Get hashed password for "password123"
    new_password = "password123"
    hashed = get_password_hash(new_password)
    
    print("🔧 Password Hash Generator")
    print("=" * 40)
    print(f"Password: {new_password}")
    print(f"Hash: {hashed}")
    print("")
    print("Now run this SQL command to update the user:")
    print("")
    print(f"PGPASSWORD=zphere_password psql -h localhost -p 5432 -U zphere_user -d zphere_db -c \"UPDATE users SET hashed_password = '{hashed}' WHERE email = 'admin@demo-tenant.com';\"")

if __name__ == "__main__":
    main()