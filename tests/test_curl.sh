#!/bin/bash
# ETL Pipeline - cURL Test Examples
# Run these commands to test all endpoints

BASE_URL="http://localhost:5000"
DEMO_EMAIL="demo@dataagent.ai"
DEMO_PASSWORD="demo1234"

echo "==================================================================="
echo "ETL Pipeline - cURL Test Suite"
echo "==================================================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ==================== 1. REGISTER / LOGIN ====================
echo -e "\n${YELLOW}1. AUTHENTICATION${NC}"
echo "Registering new user..."

REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "password": "testpass123"
  }')

echo "Response: $REGISTER_RESPONSE"

# Extract token (adjust based on actual response format)
TOKEN=$(echo $REGISTER_RESPONSE | grep -o '"token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "Failed to get token, trying login..."
  LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
      "email": "test@example.com",
      "password": "testpass123"
    }')
  TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"token":"[^"]*' | cut -d'"' -f4)
fi

echo -e "${GREEN}Token: $TOKEN${NC}\n"

# ==================== 2. CREATE JOB ====================
echo -e "\n${YELLOW}2. CREATE JOB${NC}"
echo "Creating ETL job..."

JOB_RESPONSE=$(curl -s -X POST "$BASE_URL/api/jobs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["files"],
    "description": "Test data extraction and transformation for analysis"
  }')

echo "Response: $JOB_RESPONSE"

# Extract job ID
JOB_ID=$(echo $JOB_RESPONSE | grep -o '"jobId":"[^"]*' | cut -d'"' -f4)
echo -e "${GREEN}Job ID: $JOB_ID${NC}\n"

# ==================== 3. UPLOAD FILE ====================
echo -e "\n${YELLOW}3. UPLOAD FILE${NC}"

# Create test CSV
echo "name,age,city" > test_data.csv
echo "Alice,30,New York" >> test_data.csv
echo "Bob,25,Los Angeles" >> test_data.csv
echo "Charlie,35,Chicago" >> test_data.csv

echo "Uploading CSV file..."
UPLOAD_RESPONSE=$(curl -s -X POST "$BASE_URL/api/jobs/$JOB_ID/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_data.csv")

echo "Response: $UPLOAD_RESPONSE"

# ==================== 4. UPLOAD INVALID FILE (should fail) ====================
echo -e "\n${YELLOW}4. SECURITY TEST - Upload Invalid File Type${NC}"
echo "Attempting to upload .exe file (should be rejected)..."

# Create fake exe
echo "malware" > malicious.exe

INVALID_RESPONSE=$(curl -s -X POST "$BASE_URL/api/jobs/$JOB_ID/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@malicious.exe")

echo "Response: $INVALID_RESPONSE"
echo -e "${GREEN}(Should see 'not allowed' error)${NC}"

# ==================== 5. CHECK JOB STATUS ====================
echo -e "\n${YELLOW}5. CHECK JOB STATUS${NC}"
echo "Checking job status..."

for i in {1..3}; do
  STATUS_RESPONSE=$(curl -s "$BASE_URL/api/jobs/$JOB_ID/status" \
    -H "Authorization: Bearer $TOKEN")
  
  echo "Status check #$i:"
  echo $STATUS_RESPONSE | python -m json.tool 2>/dev/null || echo $STATUS_RESPONSE
  
  if [ $i -lt 3 ]; then
    sleep 2
  fi
done

# ==================== 6. TEST CANCEL ENDPOINT ====================
echo -e "\n${YELLOW}6. CREATE & CANCEL JOB${NC}"
echo "Creating job to cancel..."

CANCEL_JOB_RESPONSE=$(curl -s -X POST "$BASE_URL/api/jobs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["files"],
    "description": "Job to be cancelled for testing"
  }')

CANCEL_JOB_ID=$(echo $CANCEL_JOB_RESPONSE | grep -o '"jobId":"[^"]*' | cut -d'"' -f4)
echo "Created job: $CANCEL_JOB_ID"

echo "Cancelling job..."
CANCEL_RESPONSE=$(curl -s -X POST "$BASE_URL/api/jobs/$CANCEL_JOB_ID/cancel" \
  -H "Authorization: Bearer $TOKEN")

echo "Response: $CANCEL_RESPONSE"

# ==================== 7. TEST UNAUTHORIZED ACCESS ====================
echo -e "\n${YELLOW}7. SECURITY TEST - Unauthorized Access${NC}"
echo "Attempting to access job without token (should fail with 401)..."

UNAUTHORIZED=$(curl -s "$BASE_URL/api/jobs/$JOB_ID/status")
echo "Response: $UNAUTHORIZED"
echo -e "${GREEN}(Should see 'Unauthorized' error)${NC}"

# ==================== 8. TEST DOWNLOAD (may fail if job not complete) ====================
echo -e "\n${YELLOW}8. DOWNLOAD RESULTS${NC}"
echo "Attempting to download results..."

curl -s "$BASE_URL/api/jobs/$JOB_ID/download" \
  -H "Authorization: Bearer $TOKEN" \
  -o "job-results-$JOB_ID.zip" \
  -w "HTTP Status: %{http_code}\n"

if [ -f "job-results-$JOB_ID.zip" ] && [ -s "job-results-$JOB_ID.zip" ]; then
  echo -e "${GREEN}Downloaded results file (size: $(du -h job-results-$JOB_ID.zip | cut -f1))${NC}"
else
  echo "Download not yet available (job may still be processing)"
fi

# ==================== 9. CHAT ENDPOINT ====================
echo -e "\n${YELLOW}9. CHAT ENDPOINT${NC}"
echo "Sending chat message..."

CHAT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"jobId\": \"$JOB_ID\",
    \"messages\": [{\"role\": \"user\", \"content\": \"What is the data?\"}]
  }")

echo "Response: $CHAT_RESPONSE"

# ==================== CLEANUP ====================
echo -e "\n${YELLOW}CLEANUP${NC}"
rm -f test_data.csv malicious.exe

echo -e "\n${GREEN}All tests completed!${NC}\n"
echo "Note: Some requests may fail if job is still processing or hasn't completed."
echo "This is expected behavior."
