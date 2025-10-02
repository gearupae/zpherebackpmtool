#!/usr/bin/env python3
"""
Simple FastAPI server for testing login functionality
This bypasses the complex SQLAlchemy relationship issues
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Simple Zphere API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

# Test user credentials
TEST_USERS = {
    "test@example.com": {
        "password": "password123",
        "user": {
            "id": "test-user-id",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "role": "admin"
        }
    }
}

@app.get("/")
async def root():
    return {"message": "Simple Zphere API is running!"}

@app.get("/api/v1/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """Simple login endpoint for testing"""
    
    # Check if user exists
    if credentials.email not in TEST_USERS:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Check password
    user_data = TEST_USERS[credentials.email]
    if credentials.password != user_data["password"]:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Return successful login response
    return LoginResponse(
        access_token="fake-access-token-12345",
        refresh_token="fake-refresh-token-67890",
        token_type="bearer",
        user=user_data["user"]
    )

@app.get("/api/v1/auth/me")
async def get_current_user():
    """Get current user info"""
    return TEST_USERS["test@example.com"]["user"]

if __name__ == "__main__":
    print("🚀 Starting Simple Zphere API Server...")
    print("📧 Test Email: test@example.com")
    print("🔑 Test Password: password123")
    print("🌐 Server will be available at: http://localhost:8000")
    print("📚 API Docs: http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
