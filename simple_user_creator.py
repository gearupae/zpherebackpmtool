#!/usr/bin/env python3
"""
Simple script to create demo users by directly inserting into database
Bypasses SQLAlchemy model loading issues
"""
import sqlite3
import uuid
import bcrypt
from datetime import datetime

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_demo_users():
    print("🚀 Creating Demo Users via Direct DB Insert...")
    
    # Connect to SQLite database
    conn = sqlite3.connect('zphere.db')
    cursor = conn.cursor()
    
    try:
        # Check/Create organization first
        cursor.execute("SELECT * FROM organizations LIMIT 1")
        org = cursor.fetchone()
        
        org_id = None
        if not org:
            print("📋 Creating demo organization...")
            org_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO organizations (
                    id, name, slug, description, domain, is_active, 
                    subscription_tier, max_users, max_projects, database_created,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                org_id, "Demo Organization", "demo-org", 
                "Demo organization for testing", "demo.com", True,
                "premium", 50, 100, True,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat()
            ))
            print(f"✅ Organization created")
        else:
            org_id = org[0]  # First column is id
            print(f"✅ Using existing organization")
        
        # Check if admin user exists
        cursor.execute("SELECT * FROM users WHERE email = ?", ("admin@zphere.com",))
        admin_exists = cursor.fetchone()
        
        if not admin_exists:
            print("👑 Creating admin user...")
            admin_id = str(uuid.uuid4())
            admin_password = hash_password("admin123")
            
            cursor.execute("""
                INSERT INTO users (
                    id, email, username, first_name, last_name, hashed_password,
                    organization_id, role, status, is_active, is_verified, timezone,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                admin_id, "admin@zphere.com", "admin", "Admin", "User", admin_password,
                org_id, "admin", "active", True, True, "UTC",
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat()
            ))
            print("✅ Admin user created")
        else:
            print("✅ Admin user already exists")
        
        # Check if tenant user exists
        cursor.execute("SELECT * FROM users WHERE email = ?", ("tenant@demo.com",))
        tenant_exists = cursor.fetchone()
        
        if not tenant_exists:
            print("👤 Creating tenant user...")
            tenant_id = str(uuid.uuid4())
            tenant_password = hash_password("tenant123")
            
            cursor.execute("""
                INSERT INTO users (
                    id, email, username, first_name, last_name, hashed_password,
                    organization_id, role, status, is_active, is_verified, timezone,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tenant_id, "tenant@demo.com", "tenant", "Tenant", "User", tenant_password,
                org_id, "tenant", "active", True, True, "UTC",
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat()
            ))
            print("✅ Tenant user created")
        else:
            print("✅ Tenant user already exists")
        
        # Commit changes
        conn.commit()
        
        print("\n" + "=" * 60)
        print("🎉 DEMO USERS CREATED SUCCESSFULLY!")
        print("=" * 60)
        
        print("\n🛡️ ADMIN LOGIN:")
        print("   Email: admin@zphere.com")
        print("   Password: admin123")
        print("   Role: ADMIN")
        
        print("\n👤 TENANT LOGIN:")
        print("   Email: tenant@demo.com")
        print("   Password: tenant123")
        print("   Role: TENANT")
        
        print("\n🌐 LOGIN URL:")
        print("   Frontend: http://localhost:3000/login")
        print("   Backend API: http://localhost:8000/api/v1/docs")
        
        print("\n✅ Ready to test login on frontend!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_demo_users()
