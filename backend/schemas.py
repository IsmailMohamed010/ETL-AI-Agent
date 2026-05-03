"""
Pydantic models for request/response validation.
Defines data structures for the API.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class FileTypeEnum(str, Enum):
    """Supported file types."""
    CSV = "csv"
    XLSX = "xlsx"
    XLS = "xls"

class ProcessingStatusEnum(str, Enum):
    """Processing job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ExtractorTypeEnum(str, Enum):
    """Types of extractors available."""
    FILE = "file"
    DATABASE = "database"
    WEB = "web"

# ─────────────────────────────────────────────────────────────────────────────
# Request Models
# ─────────────────────────────────────────────────────────────────────────────

class FileExtractionRequest(BaseModel):
    """Request model for file extraction."""
    extractor_type: ExtractorTypeEnum = Field(
        ExtractorTypeEnum.FILE,
        description="Type of extractor to use"
    )
    detect_relationships: bool = Field(
        True,
        description="Whether to detect relationships in data"
    )
    save_to_database: bool = Field(
        True,
        description="Whether to save results to database"
    )
    save_to_csv: bool = Field(
        True,
        description="Whether to save results to CSV"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "extractor_type": "file",
                "detect_relationships": True,
                "save_to_database": True,
                "save_to_csv": True
            }
        }

class DatabaseExtractionRequest(BaseModel):
    """Request model for database extraction."""
    connection_string: str = Field(
        ...,
        description="Database connection string"
    )
    query: str = Field(
        ...,
        description="SQL query to execute"
    )
    output_format: str = Field(
        "csv",
        description="Output format (csv, json)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "connection_string": "postgresql://user:password@localhost/db",
                "query": "SELECT * FROM users",
                "output_format": "csv"
            }
        }

class WebScraperRequest(BaseModel):
    """Request model for web scraping."""
    urls: List[str] = Field(
        ...,
        description="List of URLs to scrape"
    )
    selectors: Optional[Dict[str, str]] = Field(
        None,
        description="CSS selectors for data extraction"
    )

    @validator('urls')
    def validate_urls(cls, v):
        if not v:
            raise ValueError("At least one URL is required")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "urls": ["https://example.com"],
                "selectors": {"title": "h1", "content": ".main"}
            }
        }

# ─────────────────────────────────────────────────────────────────────────────
# Response Models
# ─────────────────────────────────────────────────────────────────────────────

class ExtractionResultBase(BaseModel):
    """Base model for extraction results."""
    id: str = Field(..., description="Unique job ID")
    status: ProcessingStatusEnum = Field(..., description="Processing status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    records_count: int = Field(0, description="Number of records extracted")
    file_path: Optional[str] = Field(None, description="Path to output file")
    error: Optional[str] = Field(None, description="Error message if failed")

class FileExtractionResult(ExtractionResultBase):
    """Response model for file extraction."""
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Extracted data")
    detected_relationships: Optional[Dict[str, Any]] = Field(None, description="Detected relationships")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "job_12345",
                "status": "completed",
                "timestamp": "2024-01-15T10:30:00",
                "records_count": 1000,
                "file_path": "results/output.csv",
                "extracted_data": {"sheet1": [{"col1": "value1"}]},
                "detected_relationships": {"relation1": "schema"}
            }
        }

class ProcessingJobResponse(BaseModel):
    """Response model for processing job creation."""
    job_id: str = Field(..., description="Unique job ID")
    status: ProcessingStatusEnum = Field(..., description="Current job status")
    message: str = Field(..., description="Status message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    estimated_completion_time: Optional[int] = Field(None, description="Estimated time in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_12345",
                "status": "processing",
                "message": "Extracting data from uploaded files",
                "timestamp": "2024-01-15T10:30:00",
                "estimated_completion_time": 120
            }
        }

class JobStatusResponse(BaseModel):
    """Response model for job status check."""
    job_id: str
    status: ProcessingStatusEnum
    progress: int = Field(0, ge=0, le=100, description="Progress percentage")
    message: str
    result: Optional[Dict[str, Any]] = None
    timestamp: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_12345",
                "status": "processing",
                "progress": 50,
                "message": "Processing in progress...",
                "result": None,
                "timestamp": "2024-01-15T10:30:00"
            }
        }

class HealthCheckResponse(BaseModel):
    """Response model for health check."""
    status: str = Field("healthy", description="System status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(..., description="API version")

class ErrorResponse(BaseModel):
    """Response model for errors."""
    detail: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Invalid file type. Allowed types: csv, xlsx, xls",
                "error_code": "INVALID_FILE_TYPE",
                "timestamp": "2024-01-15T10:30:00"
            }
        }
