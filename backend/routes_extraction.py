"""
API routes for ETL pipeline endpoints.
Provides REST API for file upload, extraction, transformation, and loading.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional
import os
import shutil
from pathlib import Path
import logging
from datetime import datetime
import json

from config import settings
from schemas import (
    FileExtractionRequest, FileExtractionResult, ProcessingJobResponse,
    JobStatusResponse, ErrorResponse, ProcessingStatusEnum
)
from processing import processing_service, run_etl_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/extraction", tags=["extraction"])

# ─────────────────────────────────────────────────────────────────────────────
# ETL Pipeline Endpoints (New Integrated Pipeline)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/etl-pipeline", response_model=ProcessingJobResponse)
async def run_full_etl_pipeline(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    load_to_csv: bool = Form(True),
    load_to_json: bool = Form(True),
    load_to_sqlite: bool = Form(True),
    transform_type: str = Form("full", description="full, clean, or standardize"),
):
    """
    Upload a file and run complete ETL pipeline (Extract → Transform → Load).
    
    **Parameters:**
    - `file`: CSV or XLSX file to process
    - `load_to_csv`: Save results to CSV (default: true)
    - `load_to_json`: Save results to JSON (default: true)
    - `load_to_sqlite`: Save results to SQLite database (default: true)
    - `transform_type`: Type of transformation - "full", "clean", or "standardize"
    
    **Returns:**
    - Job ID for tracking progress
    - Job status
    - Estimated completion time
    
    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/extraction/etl-pipeline" \\
      -F "file=@data.csv" \\
      -F "load_to_csv=true" \\
      -F "load_to_json=true" \\
      -F "load_to_sqlite=true"
    ```
    """
    try:
        # Validate file
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Validate file type
        if not any(file.filename.lower().endswith(f".{ext}") for ext in settings.allowed_extensions):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.filename}. Allowed: {', '.join(settings.allowed_extensions)}"
            )
        
        # Save uploaded file
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        content = await file.read()
        file_size = len(content)
        
        if file_size > settings.max_upload_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file.filename}. Max size: {settings.max_upload_size / 1024 / 1024:.1f}MB"
            )
        
        # Save file temporarily
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"Uploaded file: {file.filename} ({file_size / 1024:.2f}KB)")
        
        # Prepare load destinations
        destinations = []
        if load_to_csv:
            destinations.append("csv")
        if load_to_json:
            destinations.append("json")
        if load_to_sqlite:
            destinations.append("sqlite")
        
        if not destinations:
            destinations = ["csv"]
        
        # Create job
        job_id = processing_service.create_job(
            job_type="etl_pipeline",
            input_data={
                "file": file.filename,
                "file_path": str(file_path),
                "file_size": file_size,
                "load_destinations": destinations,
                "transform_type": transform_type
            }
        )
        
        # Start background processing
        if background_tasks:
            output_dir = upload_dir / "results" / job_id
            background_tasks.add_task(
                _run_pipeline_background,
                job_id,
                str(file_path),
                str(output_dir),
                destinations,
                transform_type
            )
        
        return ProcessingJobResponse(
            job_id=job_id,
            status=ProcessingStatusEnum.PENDING,
            message=f"ETL pipeline started for {file.filename} ({file_size / 1024:.2f}KB)",
            estimated_completion_time=120
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ETL pipeline: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting pipeline: {str(e)}")


def _run_pipeline_background(
    job_id: str,
    input_file: str,
    output_dir: str,
    destinations: List[str],
    transform_type: str
):
    """Background task to run ETL pipeline."""
    try:
        logger.info(f"[Job {job_id}] Starting background ETL pipeline execution")
        processing_service.update_job_status(
            job_id,
            ProcessingStatusEnum.PROCESSING,
            progress=5
        )
        
        # Run the complete pipeline
        result = run_etl_pipeline(
            input_file=input_file,
            output_dir=output_dir,
            load_destinations=destinations,
            transform_type=transform_type
        )
        
        # Update job with results
        if result["status"] == "success":
            processing_service.update_job_status(
                job_id,
                ProcessingStatusEnum.COMPLETED,
                progress=100,
                result=result
            )
            logger.info(f"[Job {job_id}] ✅ Pipeline completed successfully")
        else:
            processing_service.update_job_status(
                job_id,
                ProcessingStatusEnum.FAILED,
                error=result.get("error", "Unknown error"),
                progress=0
            )
            logger.error(f"[Job {job_id}] ❌ Pipeline failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"[Job {job_id}] ❌ Pipeline execution error: {str(e)}")
        processing_service.update_job_status(
            job_id,
            ProcessingStatusEnum.FAILED,
            error=str(e),
            progress=0
        )

# ─────────────────────────────────────────────────────────────────────────────

@router.post("/upload-and-process", response_model=ProcessingJobResponse)
async def upload_and_process(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    detect_relationships: bool = Form(True),
    save_to_database: bool = Form(True),
    save_to_csv: bool = Form(True),
):
    """
    Upload files and start extraction process.
    
    **Parameters:**
    - `files`: One or more CSV/XLSX files to process
    - `detect_relationships`: Detect relationships between tables (default: true)
    - `save_to_database`: Save results to database (default: true)
    - `save_to_csv`: Save results to CSV (default: true)
    
    **Returns:**
    - Job ID for tracking progress
    - Current job status
    - Estimated completion time
    
    **Example:**
    ```
    curl -X POST "http://localhost:8000/api/v1/extraction/upload-and-process" \\
      -F "files=@data.csv" \\
      -F "files=@data.xlsx" \\
      -F "detect_relationships=true"
    ```
    """
    try:
        # Validate files
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Validate file types and sizes
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        total_size = 0
        
        for file in files:
            # Check file extension
            if not any(file.filename.lower().endswith(f".{ext}") for ext in settings.allowed_extensions):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type: {file.filename}. Allowed: {', '.join(settings.allowed_extensions)}"
                )
            
            # Check file size
            content = await file.read()
            file_size = len(content)
            total_size += file_size
            
            if file_size > settings.max_upload_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large: {file.filename}. Max size: {settings.max_upload_size / 1024 / 1024}MB"
                )
            
            # Save file
            file_path = upload_dir / file.filename
            with open(file_path, "wb") as f:
                f.write(content)
            
            saved_files.append({
                "file_name": file.filename,
                "file_path": str(file_path),
                "file_type": file.filename.split(".")[-1].lower(),
                "file_size": file_size
            })
            
            logger.info(f"Uploaded file: {file.filename} ({file_size} bytes)")
        
        # Create processing job
        job_id = processing_service.create_job(
            job_type="file_extraction",
            input_data={
                "files": saved_files,
                "options": {
                    "detect_relationships": detect_relationships,
                    "save_to_database": save_to_database,
                    "save_to_csv": save_to_csv,
                }
            }
        )
        
        # Start background processing
        if background_tasks:
            options = {
                "detect_relationships": detect_relationships,
                "save_to_database": save_to_database,
                "save_to_csv": save_to_csv,
            }
            background_tasks.add_task(
                processing_service.process_file_extraction,
                job_id,
                saved_files,
                options
            )
        
        return ProcessingJobResponse(
            job_id=job_id,
            status=ProcessingStatusEnum.PENDING,
            message=f"Processing job created. Processing {len(saved_files)} file(s) ({total_size / 1024:.2f}KB)",
            estimated_completion_time=60
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading files: {str(e)}")


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a processing job.
    
    **Parameters:**
    - `job_id`: Job ID from upload-and-process endpoint
    
    **Returns:**
    - Current job status
    - Progress percentage (0-100)
    - Result data (when completed)
    
    **Example:**
    ```
    curl "http://localhost:8000/api/v1/extraction/jobs/abc123/status"
    ```
    """
    job = processing_service.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress", 0),
        message=f"Job status: {job['status'].value}",
        result=job.get("result"),
        timestamp=job.get("updated_at", datetime.utcnow())
    )


@router.get("/jobs/{job_id}/result", response_model=FileExtractionResult)
async def get_job_result(job_id: str):
    """
    Get detailed results of a completed extraction job.
    
    **Parameters:**
    - `job_id`: Job ID from upload-and-process endpoint
    
    **Returns:**
    - Extracted data
    - Detected relationships
    - Output file path
    
    **Example:**
    ```
    curl "http://localhost:8000/api/v1/extraction/jobs/abc123/result"
    ```
    """
    job = processing_service.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job["status"] != ProcessingStatusEnum.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Current status: {job['status'].value}"
        )
    
    result = job.get("result", {})
    
    return FileExtractionResult(
        id=job_id,
        status=job["status"],
        timestamp=job.get("updated_at", datetime.utcnow()),
        records_count=result.get("total_records", 0),
        file_path=result.get("output_file"),
        extracted_data=result.get("extracted_data"),
        detected_relationships=result.get("detected_relationships")
    )


@router.get("/jobs/{job_id}/download")
async def download_job_results(job_id: str):
    """
    Download extraction results as a file.
    
    **Parameters:**
    - `job_id`: Job ID from upload-and-process endpoint
    
    **Returns:**
    - ZIP file containing all results (CSV files)
    
    **Example:**
    ```
    curl -O "http://localhost:8000/api/v1/extraction/jobs/abc123/download"
    ```
    """
    job = processing_service.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job["status"] != ProcessingStatusEnum.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Current status: {job['status'].value}"
        )
    
    result = job.get("result", {})
    output_dir = result.get("output_file")
    
    if not output_dir or not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail="Results directory not found")
    
    # Create ZIP file
    import shutil
    zip_path = Path(output_dir).parent / f"{job_id}_results.zip"
    
    try:
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", output_dir)
        return FileResponse(path=zip_path, filename=f"{job_id}_results.zip")
    except Exception as e:
        logger.error(f"Error creating ZIP file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error downloading results")


@router.get("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """
    Cancel a processing job.
    
    **Parameters:**
    - `job_id`: Job ID from upload-and-process endpoint
    
    **Returns:**
    - Confirmation of cancellation
    
    **Example:**
    ```
    curl "http://localhost:8000/api/v1/extraction/jobs/abc123/cancel"
    ```
    """
    job = processing_service.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job["status"] in [ProcessingStatusEnum.COMPLETED, ProcessingStatusEnum.FAILED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {job['status'].value}"
        )
    
    processing_service.update_job_status(
        job_id,
        ProcessingStatusEnum.FAILED,
        error="Cancelled by user"
    )
    
    return JSONResponse(content={
        "job_id": job_id,
        "status": "cancelled",
        "message": "Job cancelled successfully"
    })
