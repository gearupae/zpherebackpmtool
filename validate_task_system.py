#!/usr/bin/env python3
"""
Comprehensive validation script for the task system including database schema and API endpoints
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
import requests

def print_section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_subsection(title):
    print(f"\n{'-'*40}")
    print(f" {title}")
    print(f"{'-'*40}")

def check_database_schema():
    """Check if the database schema has the required tables and columns"""
    print_section("DATABASE SCHEMA VALIDATION")
    
    try:
        # Use the same database URL as alembic
        database_url = "postgresql+psycopg2://zphere_user:zphere_password@localhost:5432/zphere_db"
        engine = create_engine(database_url)
        inspector = inspect(engine)
        
        # Check required tables
        required_tables = ['tasks', 'task_comments', 'task_attachments', 'task_documents']
        existing_tables = inspector.get_table_names()
        
        print("📋 Table Validation:")
        for table in required_tables:
            if table in existing_tables:
                print(f"  ✅ {table} - EXISTS")
                
                # Check columns for each table
                columns = inspector.get_columns(table)
                column_names = [col['name'] for col in columns]
                
                if table == 'tasks':
                    required_cols = ['id', 'title', 'description', 'status', 'priority', 'creator_id']
                    print(f"    Columns: {', '.join(column_names)}")
                elif table == 'task_comments':
                    required_cols = ['id', 'task_id', 'content', 'user_id', 'mentions', 'created_at']
                    print(f"    Columns: {', '.join(column_names)}")
                    if 'mentions' in column_names:
                        print(f"    ✅ mentions column present for @mentions feature")
                elif table == 'task_attachments':
                    required_cols = ['id', 'task_id', 'file_name', 'file_path', 'file_size']
                    print(f"    Columns: {', '.join(column_names)}")
                elif table == 'task_documents':
                    required_cols = ['id', 'task_id', 'title', 'content', 'document_type', 'version']
                    print(f"    Columns: {', '.join(column_names)}")
                
                missing_cols = [col for col in required_cols if col not in column_names]
                if missing_cols:
                    print(f"    ⚠️  Missing columns: {', '.join(missing_cols)}")
                else:
                    print(f"    ✅ All required columns present")
                    
            else:
                print(f"  ❌ {table} - MISSING")
        
        # Check if we can connect and run a simple query
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"))
            table_count = result.scalar()
            print(f"\n📊 Total tables in database: {table_count}")
            
        print("\n✅ Database connection successful")
        return True
        
    except Exception as e:
        print(f"\n❌ Database validation failed: {str(e)}")
        return False

def check_backend_server():
    """Check if backend server is running and accessible"""
    print_section("BACKEND SERVER VALIDATION")
    
    try:
        # Check health endpoint
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Server health check passed")
            print(f"   Status: {health_data.get('status', 'unknown')}")
            print(f"   Version: {health_data.get('version', 'unknown')}")
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to backend server: {str(e)}")
        return False

    # Test task endpoints (expecting 401 due to authentication)
    print_subsection("Task API Endpoints")
    endpoints = [
        ("GET", "/api/v1/tasks"),
        ("GET", "/api/v1/tasks/test-id/comments"),
        ("GET", "/api/v1/tasks/test-id/attachments"),
        ("GET", "/api/v1/tasks/test-id/documents"),
        ("GET", "/api/v1/tasks/test-id/activities"),
    ]
    
    for method, endpoint in endpoints:
        try:
            response = requests.get(f"http://localhost:8000{endpoint}", timeout=5)
            if response.status_code == 401:
                print(f"  ✅ {method} {endpoint} - Endpoint exists (401 auth required)")
            elif response.status_code == 404:
                print(f"  ❌ {method} {endpoint} - Endpoint not found")
            else:
                print(f"  ⚠️  {method} {endpoint} - Unexpected status {response.status_code}")
        except Exception as e:
            print(f"  ❌ {method} {endpoint} - Connection error: {str(e)}")
    
    return True

def check_frontend_build():
    """Check if frontend builds successfully"""
    print_section("FRONTEND BUILD VALIDATION")
    
    frontend_path = "/Users/ajaskv/Project/zphere/frontend"
    if not os.path.exists(frontend_path):
        print("❌ Frontend directory not found")
        return False
    
    try:
        # Try to build the frontend
        print("🔨 Building frontend project...")
        result = subprocess.run(
            ["npm", "run", "build"], 
            cwd=frontend_path, 
            capture_output=True, 
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print("✅ Frontend build successful")
            return True
        else:
            print("❌ Frontend build failed")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("❌ Frontend build timed out")
        return False
    except Exception as e:
        print(f"❌ Frontend build error: {str(e)}")
        return False

def validate_task_files():
    """Validate task-related files exist"""
    print_section("FILE STRUCTURE VALIDATION")
    
    files_to_check = [
        # Backend files
        ("/Users/ajaskv/Project/zphere/backend/app/models/task.py", "Task models"),
        ("/Users/ajaskv/Project/zphere/backend/app/models/task_document.py", "Task document models"),
        ("/Users/ajaskv/Project/zphere/backend/app/api/api_v1/endpoints/tasks.py", "Task API routes"),
        
        # Frontend files  
        ("/Users/ajaskv/Project/zphere/frontend/src/pages/Tasks/TaskDetailOverviewPage.tsx", "Task detail page"),
        ("/Users/ajaskv/Project/zphere/frontend/src/components/Comments/TaskComments.tsx", "Task comments component"),
        ("/Users/ajaskv/Project/zphere/frontend/src/components/Attachments/TaskAttachments.tsx", "Task attachments component"),
        ("/Users/ajaskv/Project/zphere/frontend/src/components/Documents/TaskDocuments.tsx", "Task documents component"),
    ]
    
    for file_path, description in files_to_check:
        if os.path.exists(file_path):
            print(f"✅ {description} - {file_path}")
        else:
            print(f"❌ {description} - MISSING: {file_path}")

def main():
    """Run all validation checks"""
    print_section("ZPHERE TASK SYSTEM VALIDATION")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    results = []
    
    # Run all validation checks
    results.append(("Database Schema", check_database_schema()))
    results.append(("Backend Server", check_backend_server())) 
    results.append(("Frontend Build", check_frontend_build()))
    
    # File structure check (always runs)
    validate_task_files()
    
    # Summary
    print_section("VALIDATION SUMMARY")
    
    passed = sum(1 for name, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {name}: {status}")
    
    print(f"\n📊 Overall: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All validations passed! The task system is ready for use.")
        print("\nNext steps:")
        print("- Test the task detail page at: http://localhost:3000/tasks/[task-id]")
        print("- Create test data to validate comment, attachment, and document features") 
        print("- Set up proper authentication tokens for API testing")
    else:
        print("\n⚠️ Some validations failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)