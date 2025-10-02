#!/bin/bash

# Test customer creation with curl
# First, let's get a token by logging in

echo "🔐 Getting authentication token..."

# Login to get token
LOGIN_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "tenant@zphere.com",
    "password": "password123"
  }')

echo "📋 Login Response: $LOGIN_RESPONSE"

# Extract token from response
TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "❌ Failed to get token"
  exit 1
fi

echo "✅ Token obtained: ${TOKEN:0:50}..."

echo ""
echo "🧪 Testing customer creation..."

# Test customer creation
CUSTOMER_RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "http://localhost:8000/api/v1/customers/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Type: tenant" \
  -H "X-Tenant-Slug: zphere" \
  -H "X-Tenant-Id: f8c917b6-4c39-4ad4-a6ce-afdb4b8afe4e" \
  -d '{
    "first_name": "Test",
    "last_name": "Customer",
    "email": "test.customer@example.com",
    "phone": "+1234567890",
    "company_name": "Test Company",
    "customer_type": "prospect",
    "payment_terms": "net_30",
    "tags": [],
    "custom_fields": {}
  }')

# Extract HTTP status
HTTP_STATUS=$(echo $CUSTOMER_RESPONSE | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
RESPONSE_BODY=$(echo $CUSTOMER_RESPONSE | sed -e 's/HTTPSTATUS:.*$//')

echo "📊 HTTP Status: $HTTP_STATUS"
echo "📦 Response Body: $RESPONSE_BODY"

if [ "$HTTP_STATUS" -eq 201 ]; then
  echo "✅ SUCCESS: Customer created successfully!"
elif [ "$HTTP_STATUS" -eq 403 ]; then
  echo "❌ FORBIDDEN: Permission denied"
  echo "🔍 Check user permissions and role"
elif [ "$HTTP_STATUS" -eq 401 ]; then
  echo "❌ UNAUTHORIZED: Authentication failed"
  echo "🔍 Token may be invalid or expired"
else
  echo "❌ UNEXPECTED STATUS: $HTTP_STATUS"
fi

echo ""
echo "🔍 Testing authentication with GET request..."

# Test with GET to see if auth works
GET_RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" -X GET "http://localhost:8000/api/v1/customers/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-Type: tenant" \
  -H "X-Tenant-Slug: zphere" \
  -H "X-Tenant-Id: f8c917b6-4c39-4ad4-a6ce-afdb4b8afe4e")

GET_HTTP_STATUS=$(echo $GET_RESPONSE | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
GET_RESPONSE_BODY=$(echo $GET_RESPONSE | sed -e 's/HTTPSTATUS:.*$//')

echo "📊 GET HTTP Status: $GET_HTTP_STATUS"
echo "📦 GET Response: $GET_RESPONSE_BODY"
