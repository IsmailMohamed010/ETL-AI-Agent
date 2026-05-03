"""
Test suite for ETL Pipeline API.
Run with: pytest test_api.py
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from main import app
from config import settings
from processing import processing_service
import tempfile
from pathlib import Path
import pandas as pd

# Create test client
client = TestClient(app)

# ─────────────────────────────────────────────────────────────────────────────
# Health Check Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "version" in response.json()


def test_api_info():
    """Test API info endpoint."""
    response = client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == settings.app_name
    assert "supported_file_types" in data
    assert "csv" in data["supported_file_types"]


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data

# ─────────────────────────────────────────────────────────────────────────────
# File Upload Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_csv_file():
    """Create a sample CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("id,name,email\n")
        f.write("1,John,john@example.com\n")
        f.write("2,Jane,jane@example.com\n")
        return f.name


@pytest.fixture
def sample_excel_file():
    """Create a sample Excel file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'product': ['A', 'B', 'C'],
            'price': [100, 200, 300]
        })
        df.to_excel(f.name, index=False)
        return f.name


def test_upload_csv_file(sample_csv_file):
    """Test uploading a CSV file."""
    with open(sample_csv_file, 'rb') as f:
        response = client.post(
            "/api/v1/extraction/upload-and-process",
            files={"files": ("test.csv", f, "text/csv")},
            data={
                "detect_relationships": "true",
                "save_to_database": "true",
                "save_to_csv": "true"
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"
    assert "message" in data


def test_upload_multiple_files(sample_csv_file, sample_excel_file):
    """Test uploading multiple files."""
    with open(sample_csv_file, 'rb') as csv, \
         open(sample_excel_file, 'rb') as xlsx:
        response = client.post(
            "/api/v1/extraction/upload-and-process",
            files=[
                ("files", ("test.csv", csv, "text/csv")),
                ("files", ("test.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
            ],
            data={
                "detect_relationships": "true",
                "save_to_csv": "true"
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data


def test_upload_invalid_file_type():
    """Test uploading unsupported file type."""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
        f.write(b"Invalid file type")
        f.flush()
        
        with open(f.name, 'rb') as txt:
            response = client.post(
                "/api/v1/extraction/upload-and-process",
                files={"files": ("test.txt", txt, "text/plain")},
            )
    
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_upload_no_files():
    """Test uploading with no files."""
    response = client.post(
        "/api/v1/extraction/upload-and-process",
        data={
            "detect_relationships": "true",
            "save_to_csv": "true"
        }
    )
    
    assert response.status_code == 400

# ─────────────────────────────────────────────────────────────────────────────
# Job Status Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_get_job_status(sample_csv_file):
    """Test getting job status."""
    # Upload file
    with open(sample_csv_file, 'rb') as f:
        response = client.post(
            "/api/v1/extraction/upload-and-process",
            files={"files": ("test.csv", f, "text/csv")}
        )
    
    job_id = response.json()["job_id"]
    
    # Check status
    status_response = client.get(f"/api/v1/extraction/jobs/{job_id}/status")
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["job_id"] == job_id
    assert data["status"] in ["pending", "processing", "completed", "failed"]
    assert "progress" in data


def test_get_nonexistent_job_status():
    """Test getting status of non-existent job."""
    response = client.get("/api/v1/extraction/jobs/nonexistent-job-id/status")
    assert response.status_code == 404


def test_cancel_job(sample_csv_file):
    """Test canceling a job."""
    # Upload file
    with open(sample_csv_file, 'rb') as f:
        response = client.post(
            "/api/v1/extraction/upload-and-process",
            files={"files": ("test.csv", f, "text/csv")}
        )
    
    job_id = response.json()["job_id"]
    
    # Cancel job
    cancel_response = client.get(f"/api/v1/extraction/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200
    assert "cancelled" in cancel_response.json()["status"]

# ─────────────────────────────────────────────────────────────────────────────
# Processing Service Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_create_job():
    """Test creating a processing job."""
    job_id = processing_service.create_job(
        job_type="file_extraction",
        input_data={"files": []}
    )
    
    assert job_id is not None
    job = processing_service.get_job_status(job_id)
    assert job is not None
    assert job["type"] == "file_extraction"
    assert job["status"].value == "pending"


def test_update_job_status():
    """Test updating job status."""
    job_id = processing_service.create_job(
        job_type="file_extraction",
        input_data={}
    )
    
    processing_service.update_job_status(
        job_id,
        "processing",
        progress=50
    )
    
    job = processing_service.get_job_status(job_id)
    assert job["status"] == "processing"
    assert job["progress"] == 50

# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_full_workflow(sample_csv_file):
    """Test complete extraction workflow."""
    # 1. Upload file
    with open(sample_csv_file, 'rb') as f:
        upload_response = client.post(
            "/api/v1/extraction/upload-and-process",
            files={"files": ("test.csv", f, "text/csv")},
            data={"detect_relationships": "true"}
        )
    
    assert upload_response.status_code == 200
    job_id = upload_response.json()["job_id"]
    
    # 2. Poll status until completion (with timeout)
    import time
    start_time = time.time()
    timeout = 30
    
    while time.time() - start_time < timeout:
        status_response = client.get(f"/api/v1/extraction/jobs/{job_id}/status")
        assert status_response.status_code == 200
        
        status = status_response.json()["status"]
        if status == "completed":
            break
        elif status == "failed":
            pytest.fail("Job processing failed")
        
        time.sleep(1)
    
    # 3. Get results
    result_response = client.get(f"/api/v1/extraction/jobs/{job_id}/result")
    
    if result_response.status_code == 200:
        result = result_response.json()
        assert "extracted_data" in result
        assert result["status"] == "completed"

# ─────────────────────────────────────────────────────────────────────────────
# Error Handling Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_error_response_format():
    """Test error response format."""
    response = client.get("/api/v1/extraction/jobs/invalid/status")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "error_code" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
