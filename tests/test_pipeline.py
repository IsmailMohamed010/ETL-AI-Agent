"""
Comprehensive Test Suite for ETL Pipeline
Tests all endpoints, security, persistence, and error handling
"""

import os
import sys
import json
import requests
import time
import tempfile
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:5000"
DEMO_EMAIL = "demo@dataagent.ai"
DEMO_PASSWORD = "demo1234"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpass123"

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_section(title):
    """Print a test section header"""
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}{title:^80}{RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}\n")


def print_success(msg):
    """Print success message"""
    print(f"{GREEN}✓ {msg}{RESET}")


def print_error(msg):
    """Print error message"""
    print(f"{RED}✗ {msg}{RESET}")


def print_info(msg):
    """Print info message"""
    print(f"{YELLOW}→ {msg}{RESET}")


def test_server_health():
    """Test 1: Server Health Check"""
    print_section("Test 1: Server Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print_success("Server is running")
            return True
        else:
            print_error(f"Server returned {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Cannot connect to server: {e}")
        return False


def test_authentication():
    """Test 2: Authentication (Login & Register)"""
    print_section("Test 2: Authentication")
    
    # Test 2.1: Register new user
    print_info("Testing user registration...")
    try:
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Test User",
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code in [201, 409]:  # 201 created or 409 already exists
            data = response.json()
            if "token" in data:
                token = data["token"]
                print_success(f"User registration successful (got token)")
            else:
                print_info("User already exists, attempting login...")
                response = requests.post(f"{BASE_URL}/api/auth/login", json={
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD
                })
                if response.status_code == 200:
                    token = response.json()["token"]
                    print_success("User login successful")
                else:
                    print_error("Login failed")
                    return None
        else:
            print_error(f"Registration failed: {response.status_code}")
            return None
    except Exception as e:
        print_error(f"Authentication error: {e}")
        return None
    
    return token


def test_job_creation(token):
    """Test 3: Job Creation"""
    print_section("Test 3: Job Creation")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "sources": ["files"],
                "description": "Test data extraction and transformation for analysis"
            }
        )
        
        if response.status_code == 201:
            data = response.json()
            required_fields = ["jobId", "status", "message", "createdAt", "progress"]
            
            missing = [f for f in required_fields if f not in data]
            if missing:
                print_error(f"Response missing fields: {missing}")
                return None
            
            print_success(f"Job created: {data['jobId']}")
            print_info(f"Status: {data['status']}")
            print_info(f"Progress: {data['progress']}%")
            print_info(f"Message: {data['message']}")
            
            return data["jobId"]
        else:
            print_error(f"Job creation failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
    except Exception as e:
        print_error(f"Error: {e}")
        return None


def test_file_upload(token, job_id):
    """Test 4: File Upload with Validation"""
    print_section("Test 4: File Upload with Validation")
    
    # Test 4.1: Valid CSV file
    print_info("Test 4.1: Uploading valid CSV file...")
    try:
        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,age,city\n")
            f.write("Alice,30,NYC\n")
            f.write("Bob,25,LA\n")
            csv_file = f.name
        
        with open(csv_file, 'rb') as f:
            response = requests.post(
                f"{BASE_URL}/api/jobs/{job_id}/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": f}
            )
        
        if response.status_code == 200:
            print_success("Valid CSV file uploaded")
            os.unlink(csv_file)
        else:
            print_error(f"CSV upload failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            os.unlink(csv_file)
    except Exception as e:
        print_error(f"Error: {e}")
        if os.path.exists(csv_file):
            os.unlink(csv_file)
    
    # Test 4.2: Invalid file type (should fail)
    print_info("Test 4.2: Attempting to upload invalid file type (.exe)...")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.exe', delete=False) as f:
            f.write("malware")
            exe_file = f.name
        
        with open(exe_file, 'rb') as f:
            response = requests.post(
                f"{BASE_URL}/api/jobs/{job_id}/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": f}
            )
        
        if response.status_code == 400:
            print_success("Invalid file type correctly rejected (400)")
            print_info(f"Message: {response.json().get('error', 'N/A')}")
        else:
            print_error(f"Should have rejected .exe file but got {response.status_code}")
        
        os.unlink(exe_file)
    except Exception as e:
        print_error(f"Error: {e}")
        if os.path.exists(exe_file):
            os.unlink(exe_file)
    
    # Test 4.3: JSON file (valid)
    print_info("Test 4.3: Uploading valid JSON file...")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"data": [1, 2, 3]}, f)
            json_file = f.name
        
        with open(json_file, 'rb') as f:
            response = requests.post(
                f"{BASE_URL}/api/jobs/{job_id}/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": f}
            )
        
        if response.status_code == 200:
            print_success("Valid JSON file uploaded")
        else:
            print_error(f"JSON upload failed: {response.status_code}")
        
        os.unlink(json_file)
    except Exception as e:
        print_error(f"Error: {e}")
        if os.path.exists(json_file):
            os.unlink(json_file)


def test_job_status(token, job_id):
    """Test 5: Job Status Response"""
    print_section("Test 5: Job Status Response")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/jobs/{job_id}/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ["jobId", "status", "message", "progress", "error", "results", "createdAt", "updatedAt"]
            
            missing = [f for f in required_fields if f not in data]
            if missing:
                print_error(f"Response missing fields: {missing}")
            else:
                print_success("All required fields present in status response")
            
            print_info(f"Status: {data['status']}")
            print_info(f"Progress: {data['progress']}%")
            print_info(f"Message: {data['message']}")
            print_info(f"Error: {data['error']}")
            
            return True
        else:
            print_error(f"Status check failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False


def test_job_cancel(token, job_id):
    """Test 6: Cancel Job"""
    print_section("Test 6: Cancel Job")
    
    # First create a new job to cancel
    try:
        print_info("Creating a job to cancel...")
        response = requests.post(
            f"{BASE_URL}/api/jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "sources": ["files"],
                "description": "Test job for cancellation"
            }
        )
        
        if response.status_code != 201:
            print_error("Could not create job to cancel")
            return False
        
        cancel_job_id = response.json()["jobId"]
        
        # Now cancel it
        print_info(f"Cancelling job {cancel_job_id}...")
        response = requests.post(
            f"{BASE_URL}/api/jobs/{cancel_job_id}/cancel",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "cancelled":
                print_success("Job cancelled successfully")
                return True
            else:
                print_error("Job cancelled but status not updated")
                return False
        else:
            print_error(f"Cancel failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False


def test_download_endpoint(token, job_id):
    """Test 7: Download Results (may not work if job not done)"""
    print_section("Test 7: Download Results Endpoint")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/jobs/{job_id}/download",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 400:
            print_info("Job not yet complete (expected)")
            print_info(f"Response: {response.json().get('error', 'N/A')}")
        elif response.status_code == 200:
            print_success("Download endpoint working")
            print_info(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        else:
            print_error(f"Download failed: {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")


def test_chat_endpoint(token, job_id):
    """Test 8: Chat Endpoint Response"""
    print_section("Test 8: Chat Endpoint Response")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "jobId": job_id,
                "messages": [{"role": "user", "content": "What is the data?"}]
            }
        )
        
        if response.status_code == 400 or response.status_code == 200:
            if response.status_code == 400:
                print_info("Job not complete (expected)")
                print_info(f"Response: {response.json().get('error', 'N/A')}")
            else:
                data = response.json()
                required_fields = ["content", "jobId", "timestamp", "role"]
                missing = [f for f in required_fields if f not in data]
                
                if missing:
                    print_error(f"Response missing fields: {missing}")
                else:
                    print_success("Chat response has all required fields")
                    print_info(f"Role: {data['role']}")
        else:
            print_error(f"Chat failed: {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")


def test_job_persistence():
    """Test 9: Job Persistence (load from disk)"""
    print_section("Test 9: Job Persistence")
    
    jobs_file = r"c:\Users\Ahmed\ETL-AI-Agent\web\jobs.json"
    
    if os.path.exists(jobs_file):
        try:
            with open(jobs_file, 'r') as f:
                jobs = json.load(f)
            print_success(f"Jobs file exists with {len(jobs)} jobs")
            
            if len(jobs) > 0:
                first_job_id = list(jobs.keys())[0]
                print_info(f"Sample job: {first_job_id}")
                print_info(f"Status: {jobs[first_job_id].get('status', 'N/A')}")
            
            return True
        except Exception as e:
            print_error(f"Error reading jobs file: {e}")
            return False
    else:
        print_info("Jobs file doesn't exist yet (will be created on first job)")
        return True


def test_unauthorized_access(job_id):
    """Test 10: Unauthorized Access Rejection"""
    print_section("Test 10: Unauthorized Access Rejection")
    
    # Try without token
    print_info("Attempting to access job without token...")
    try:
        response = requests.get(f"{BASE_URL}/api/jobs/{job_id}/status")
        
        if response.status_code == 401:
            print_success("Unauthorized request correctly rejected (401)")
        else:
            print_error(f"Should have rejected but got {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")


def run_all_tests():
    """Run all tests"""
    print(f"\n{BLUE}{'*' * 80}{RESET}")
    print(f"{BLUE}{'ETL PIPELINE - COMPREHENSIVE TEST SUITE':^80}{RESET}")
    print(f"{BLUE}{'*' * 80}{RESET}")
    
    # Test 1: Server Health
    if not test_server_health():
        print_error("Server is not running. Please start Flask server first:")
        print(f"  cd c:\\Users\\Ahmed\\ETL-AI-Agent\\web")
        print(f"  .\\..venv_run\\Scripts\\python app.py")
        return
    
    # Test 2: Authentication
    token = test_authentication()
    if not token:
        print_error("Could not authenticate. Stopping tests.")
        return
    
    # Test 3: Job Creation
    job_id = test_job_creation(token)
    if not job_id:
        print_error("Could not create job. Stopping tests.")
        return
    
    # Test 4: File Upload
    test_file_upload(token, job_id)
    
    # Test 5: Job Status
    test_job_status(token, job_id)
    
    # Test 6: Job Cancel
    test_job_cancel(token)
    
    # Test 7: Download
    test_download_endpoint(token, job_id)
    
    # Test 8: Chat
    test_chat_endpoint(token, job_id)
    
    # Test 9: Persistence
    test_job_persistence()
    
    # Test 10: Unauthorized
    test_unauthorized_access(job_id)
    
    # Summary
    print_section("Test Summary")
    print(f"{GREEN}All tests completed!{RESET}")
    print(f"\n{YELLOW}Note: Some tests showed expected failures (job not complete, etc.){RESET}")
    print(f"{YELLOW}This is normal during active pipeline execution.{RESET}")


if __name__ == "__main__":
    run_all_tests()
