#!/usr/bin/env python3
"""
Test API authentication and user endpoint
"""
import asyncio
import httpx
import json

async def test_api():
    # Test authentication endpoint
    auth_data = {
        "email": "admin@zphere.com", 
        "password": "admin123"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            print("🔐 Testing authentication...")
            auth_response = await client.post(
                "http://localhost:8000/api/v1/auth/login",
                json=auth_data,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"Auth status: {auth_response.status_code}")
            if auth_response.status_code != 200:
                print(f"Auth error: {auth_response.text}")
                return
            
            auth_result = auth_response.json()
            access_token = auth_result.get("access_token")
            user_data = auth_result.get("user", {})
            
            print(f"✅ Authentication successful!")
            print(f"User: {user_data.get('email')} ({user_data.get('role')})")
            print(f"Organization: {user_data.get('organization', {}).get('name')}")
            
            if not access_token:
                print("❌ No access token received")
                return
            
            # Get organization info for tenant headers
            org_id = user_data.get("organization_id")
            org_slug = user_data.get("organization", {}).get("slug") 
            user_role = user_data.get("role")
            
            print(f"\n👥 Testing users endpoint...")
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Tenant-Type": "tenant",
                "X-Tenant-Slug": org_slug or "",  
                "X-Tenant-Id": org_id or "",
            }
            
            users_response = await client.get(
                "http://localhost:8000/api/v1/users/",
                headers=headers
            )
            
            print(f"Users status: {users_response.status_code}")
            if users_response.status_code == 200:
                users = users_response.json()
                print(f"✅ Found {len(users)} users:")
                for user in users[:5]:  # Show first 5 users
                    print(f"  - {user.get('email')}: {user.get('first_name')} {user.get('last_name')}")
            else:
                print(f"❌ Users endpoint error: {users_response.text}")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())