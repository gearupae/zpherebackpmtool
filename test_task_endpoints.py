#!/usr/bin/env python3
"""
Test script to validate task API endpoints are working properly
"""

import requests
import json
import uuid
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"

def get_auth_headers():
    """Get authentication headers (you'll need to replace with actual auth)"""
    # For testing purposes - you'd need actual login credentials
    # This is a placeholder - replace with your actual auth token
    return {
        "Authorization": "Bearer YOUR_AUTH_TOKEN_HERE",
        "Content-Type": "application/json",
        "Organization-ID": "YOUR_ORG_ID_HERE"  # Multi-tenant header
    }

def test_endpoint(method, endpoint, data=None, files=None):
    """Test an API endpoint"""
    headers = get_auth_headers()
    if files:
        # Remove content-type for multipart uploads
        headers.pop("Content-Type", None)
    
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            if files:
                response = requests.post(url, headers=headers, data=data, files=files)
            else:
                response = requests.post(url, headers=headers, json=data)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        
        print(f"{method} {endpoint}")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code < 400:
            try:
                response_data = response.json()
                print("✅ Success")
                if isinstance(response_data, list):
                    print(f"Response: List with {len(response_data)} items")
                elif isinstance(response_data, dict):
                    print(f"Response keys: {list(response_data.keys())}")
            except:
                print("✅ Success (no JSON response)")
        else:
            print("❌ Error")
            try:
                print(f"Error: {response.json()}")
            except:
                print(f"Error: {response.text}")
        
        print("-" * 50)
        return response
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error - Make sure backend is running on port 8000")
        print("-" * 50)
        return None
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        print("-" * 50)
        return None

def main():
    """Test all task-related endpoints"""
    print("Testing Task API Endpoints")
    print("=" * 50)
    
    # Test basic task endpoints
    print("\n📋 Basic Task Endpoints:")
    test_endpoint("GET", "/tasks")
    
    # Test task comments endpoints  
    print("\n💬 Comment Endpoints:")
    test_endpoint("GET", "/tasks/dummy-task-id/comments")
    
    # Test task attachments endpoints
    print("\n📎 Attachment Endpoints:")
    test_endpoint("GET", "/tasks/dummy-task-id/attachments")
    
    # Test task documents endpoints
    print("\n📄 Document Endpoints:")
    test_endpoint("GET", "/tasks/dummy-task-id/documents")
    
    # Test activities endpoint
    print("\n📈 Activity Endpoints:")
    test_endpoint("GET", "/tasks/dummy-task-id/activities")
    
    print("\n" + "=" * 50)
    print("API Endpoint Testing Complete")
    print("\nNote: Some endpoints may return 404 or 401 errors due to:")
    print("- Missing authentication token")
    print("- Non-existent task IDs")
    print("- Missing organization context")
    print("\nThis is normal for endpoint structure testing.")

if __name__ == "__main__":
    main()