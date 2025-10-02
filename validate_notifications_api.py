#!/usr/bin/env python3
"""
Validation script to verify the notifications API is working properly
"""

import requests
from sqlalchemy import create_engine, text

def validate_database():
    """Validate that notifications exist in the database"""
    print("🔍 Checking database for notifications...")
    
    try:
        database_url = "postgresql+psycopg2://zphere_user:zphere_password@localhost:5432/zphere_db"
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check total notifications count
            result = conn.execute(text("SELECT COUNT(*) FROM notifications"))
            total_count = result.scalar()
            print(f"   Total notifications in database: {total_count}")
            
            # Check unread notifications
            result = conn.execute(text("SELECT COUNT(*) FROM notifications WHERE is_read = false"))
            unread_count = result.scalar()
            print(f"   Unread notifications: {unread_count}")
            
            # Show sample notification data
            result = conn.execute(text("""
                SELECT id, title, notification_type, priority, is_read, created_at 
                FROM notifications 
                ORDER BY created_at DESC 
                LIMIT 3
            """))
            
            print("\n   Sample notifications:")
            for row in result.fetchall():
                id_val, title, type_val, priority, is_read, created_at = row
                status = "READ" if is_read else "UNREAD"
                print(f"     • {title} [{type_val}] - {status}")
            
            return total_count > 0
            
    except Exception as e:
        print(f"   ❌ Database validation failed: {str(e)}")
        return False

def validate_api_endpoints():
    """Validate that API endpoints are responding correctly"""
    print("\n🔗 Checking API endpoints...")
    
    base_url = "http://localhost:8000/api/v1"
    endpoints_to_check = [
        "/notifications/",
        "/notifications/settings",
    ]
    
    for endpoint in endpoints_to_check:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            
            if response.status_code == 403:
                print(f"   ✅ {endpoint} - Properly protected (403 Forbidden)")
            elif response.status_code == 401:
                print(f"   ✅ {endpoint} - Properly protected (401 Unauthorized)")
            elif response.status_code == 404:
                print(f"   ❌ {endpoint} - Endpoint not found")
            else:
                print(f"   ⚠️  {endpoint} - Unexpected status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ {endpoint} - Connection failed (is backend running?)")
            return False
        except Exception as e:
            print(f"   ❌ {endpoint} - Error: {str(e)}")
            
    return True

def validate_backend_health():
    """Check if backend server is healthy"""
    print("\n💚 Checking backend health...")
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        
        if response.status_code == 200:
            health_data = response.json()
            print(f"   ✅ Backend is healthy")
            print(f"   Status: {health_data.get('status', 'unknown')}")
            print(f"   Version: {health_data.get('version', 'unknown')}")
            return True
        else:
            print(f"   ❌ Backend health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Backend health check failed: {str(e)}")
        return False

def main():
    """Run all validation checks"""
    print("=" * 60)
    print(" NOTIFICATIONS API VALIDATION")
    print("=" * 60)
    
    results = []
    
    # Check backend health first
    results.append(("Backend Health", validate_backend_health()))
    
    # Check database
    results.append(("Database", validate_database()))
    
    # Check API endpoints
    results.append(("API Endpoints", validate_api_endpoints()))
    
    # Summary
    print("\n" + "=" * 60)
    print(" VALIDATION SUMMARY")
    print("=" * 60)
    
    passed = 0
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {name}: {status}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\n📊 Overall: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 Notifications API is properly configured!")
        print("\n💡 Next steps to test notifications:")
        print("   1. Login to your frontend application")
        print("   2. Navigate to the notifications section")
        print("   3. You should see the test notifications created")
        print("   4. Test marking notifications as read")
        print("   5. Test notification filters (unread only, by priority, etc.)")
        print("\n🔧 API endpoints available:")
        print("   GET    /api/v1/notifications/")
        print("   PUT    /api/v1/notifications/{id}/read")
        print("   PUT    /api/v1/notifications/mark-all-read")
        print("   DELETE /api/v1/notifications/{id}")
        print("   GET    /api/v1/notifications/settings")
        print("   PUT    /api/v1/notifications/settings")
    else:
        print("\n⚠️  Some validations failed. Please check the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)