"""
Core processing logic for ETL operations.
Integrates extraction, transformation, and loading modules.
"""

import os
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

from config import settings
from schemas import ProcessingStatusEnum
from extraction import extract_data, DataExtractor
from transformation import transform_data, DataTransformer
from loading import load_data, DataLoader

logger = logging.getLogger(__name__)

class ProcessingService:
    """Service for managing ETL processing jobs."""
    
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.executor = ThreadPoolExecutor(max_workers=settings.max_workers)
    
    def create_job(self, job_type: str, input_data: Any) -> str:
        """Create a new processing job."""
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "status": ProcessingStatusEnum.PENDING,
            "created_at": datetime.utcnow(),
            "input_data": input_data,
            "progress": 0,
            "result": None,
            "error": None,
        }
        logger.info(f"Created job {job_id} of type {job_type}")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a processing job."""
        return self.jobs.get(job_id)
    
    def update_job_status(self, job_id: str, status: ProcessingStatusEnum, **kwargs):
        """Update job status and metadata."""
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = status
            self.jobs[job_id]["updated_at"] = datetime.utcnow()
            self.jobs[job_id].update(kwargs)
            logger.info(f"Updated job {job_id} status to {status}")
    
    async def process_file_extraction(self, job_id: str, files: List[Dict[str, Any]], options: Dict[str, Any]):
        """
        Process file extraction job.
        
        Args:
            job_id: Job ID
            files: List of file information
            options: Processing options
        """
        try:
            self.update_job_status(job_id, ProcessingStatusEnum.PROCESSING, progress=10)
            
            # Extract data from files
            extracted_data = {}
            total_records = 0
            
            for idx, file_info in enumerate(files):
                file_path = file_info.get("file_path")
                
                if not os.path.exists(file_path):
                    logger.warning(f"File not found: {file_path}")
                    continue
                
                # Determine file type and extract
                ext = Path(file_path).suffix.lower()[1:]
                
                try:
                    if ext == "csv":
                        df = pd.read_csv(file_path)
                        extracted_data[os.path.basename(file_path)] = df.to_dict(orient="records")
                        total_records += len(df)
                    elif ext in ["xlsx", "xls"]:
                        sheets = pd.read_excel(file_path, sheet_name=None)
                        file_data = {}
                        for sheet_name, df in sheets.items():
                            file_data[sheet_name] = df.to_dict(orient="records")
                            total_records += len(df)
                        extracted_data[os.path.basename(file_path)] = file_data
                    else:
                        logger.warning(f"Unsupported file type: {ext}")
                        continue
                except Exception as e:
                    logger.error(f"Error extracting {file_path}: {str(e)}")
                    extracted_data[os.path.basename(file_path)] = {"error": str(e)}
                
                # Update progress
                progress = 10 + (idx + 1) / len(files) * 40
                self.update_job_status(job_id, ProcessingStatusEnum.PROCESSING, progress=progress)
            
            self.update_job_status(job_id, ProcessingStatusEnum.PROCESSING, progress=60)
            
            # Detect relationships if requested
            detected_relationships = {}
            if options.get("detect_relationships", True):
                detected_relationships = self._detect_relationships(extracted_data)
                self.update_job_status(job_id, ProcessingStatusEnum.PROCESSING, progress=80)
            
            # Save results
            output_file = None
            if options.get("save_to_csv", True):
                output_file = self._save_to_csv(job_id, extracted_data)
            
            self.update_job_status(
                job_id,
                ProcessingStatusEnum.COMPLETED,
                progress=100,
                result={
                    "extracted_data": extracted_data,
                    "detected_relationships": detected_relationships,
                    "total_records": total_records,
                    "output_file": output_file,
                    "completed_at": datetime.utcnow().isoformat()
                }
            )
            logger.info(f"Completed job {job_id}: extracted {total_records} records")
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {str(e)}")
            self.update_job_status(
                job_id,
                ProcessingStatusEnum.FAILED,
                error=str(e),
                progress=0
            )
    
    def _detect_relationships(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect relationships between tables/sheets.
        Looks for common columns that might indicate foreign keys.
        """
        relationships = {}
        
        # Get all tables and their columns
        tables_columns = {}
        for file_name, data in extracted_data.items():
            if isinstance(data, dict) and isinstance(next(iter(data.values()), None), list):
                # Multiple sheets
                for sheet_name, records in data.items():
                    if records:
                        tables_columns[f"{file_name}/{sheet_name}"] = set(records[0].keys())
            elif isinstance(data, list) and data:
                tables_columns[file_name] = set(data[0].keys())
        
        # Find common columns (potential relationships)
        table_names = list(tables_columns.keys())
        for i, table1 in enumerate(table_names):
            for table2 in table_names[i+1:]:
                common_cols = tables_columns[table1] & tables_columns[table2]
                if common_cols:
                    relationship_key = f"{table1} <-> {table2}"
                    relationships[relationship_key] = list(common_cols)
        
        return relationships
    
    def _save_to_csv(self, job_id: str, extracted_data: Dict[str, Any]) -> str:
        """Save extracted data to CSV files."""
        output_dir = Path(settings.upload_dir) / "results" / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_files = []
        for file_name, data in extracted_data.items():
            try:
                if isinstance(data, dict) and isinstance(next(iter(data.values()), None), list):
                    # Multiple sheets
                    for sheet_name, records in data.items():
                        df = pd.DataFrame(records)
                        file_path = output_dir / f"{file_name}_{sheet_name}.csv"
                        df.to_csv(file_path, index=False)
                        output_files.append(str(file_path))
                elif isinstance(data, list):
                    df = pd.DataFrame(data)
                    file_path = output_dir / f"{file_name}.csv"
                    df.to_csv(file_path, index=False)
                    output_files.append(str(file_path))
            except Exception as e:
                logger.error(f"Error saving {file_name} to CSV: {str(e)}")
        
        return str(output_dir)

# Global processing service instance
processing_service = ProcessingService()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ETL PIPELINE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def run_etl_pipeline(
    input_file: str,
    output_dir: str = "output",
    load_destinations: Optional[List[str]] = None,
    transform_type: str = "full"
) -> Dict[str, Any]:
    """
    Complete ETL Pipeline: Extract → Transform → Load
    
    This is the main orchestration function that runs the full ETL process.
    
    Args:
        input_file: Path to input file (CSV or XLSX)
        output_dir: Directory to save output files
        load_destinations: List of destinations ("csv", "json", "sqlite")
        transform_type: Type of transformation ("full", "clean", "standardize")
        
    Returns:
        Dictionary with pipeline execution results
        
    Raises:
        FileNotFoundError: If input file doesn't exist
        Exception: If any step fails
        
    Example:
        >>> result = run_etl_pipeline("data.csv", output_dir="output")
        >>> print(result["status"])
        "success"
    """
    
    logger.info("=" * 80)
    logger.info("🚀 STARTING ETL PIPELINE")
    logger.info("=" * 80)
    
    if load_destinations is None:
        load_destinations = ["csv", "json", "sqlite"]
    
    pipeline_result = {
        "status": "pending",
        "start_time": datetime.utcnow().isoformat(),
        "end_time": None,
        "steps": {
            "extraction": None,
            "transformation": None,
            "loading": None
        },
        "total_records": 0,
        "error": None,
        "summary": None
    }
    
    try:
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 1: EXTRACTION
        # ─────────────────────────────────────────────────────────────────────────
        logger.info("\n" + "─" * 80)
        logger.info("STEP 1: EXTRACTION")
        logger.info("─" * 80)
        
        try:
            extraction_result = extract_data("file", file_path=input_file)
            pipeline_result["steps"]["extraction"] = {
                "status": "success",
                "records_extracted": len(extraction_result.get("data", [])),
                "file_name": extraction_result.get("file_name"),
                "format": extraction_result.get("metadata", {}).get("format"),
                "details": extraction_result.get("metadata", {})
            }
            logger.info(f"✅ Extraction complete: {len(extraction_result['data'])} records extracted")
            
        except Exception as e:
            logger.error(f"❌ Extraction failed: {str(e)}")
            pipeline_result["steps"]["extraction"] = {
                "status": "failed",
                "error": str(e)
            }
            pipeline_result["status"] = "failed"
            pipeline_result["error"] = f"Extraction error: {str(e)}"
            raise
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 2: TRANSFORMATION
        # ─────────────────────────────────────────────────────────────────────────
        logger.info("\n" + "─" * 80)
        logger.info("STEP 2: TRANSFORMATION")
        logger.info("─" * 80)
        
        try:
            transformation_result = transform_data(extraction_result, transform_type=transform_type)
            pipeline_result["steps"]["transformation"] = {
                "status": "success",
                "records_before": extraction_result.get("metadata", {}).get("rows", len(extraction_result.get("data", []))),
                "records_after": len(transformation_result.get("data", [])),
                "transforms_applied": transformation_result.get("transforms_applied", []),
                "details": {
                    "cleaning_report": transformation_result.get("cleaning_report"),
                    "duplicates_removed": transformation_result.get("duplicates_removed", 0),
                    "validation_report": transformation_result.get("validation_report")
                }
            }
            logger.info(f"✅ Transformation complete: {len(transformation_result['data'])} records after transformation")
            logger.info(f"   Transforms applied: {', '.join(transformation_result.get('transforms_applied', []))}")
            
        except Exception as e:
            logger.error(f"❌ Transformation failed: {str(e)}")
            pipeline_result["steps"]["transformation"] = {
                "status": "failed",
                "error": str(e)
            }
            pipeline_result["status"] = "failed"
            pipeline_result["error"] = f"Transformation error: {str(e)}"
            raise
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 3: LOADING
        # ─────────────────────────────────────────────────────────────────────────
        logger.info("\n" + "─" * 80)
        logger.info("STEP 3: LOADING")
        logger.info("─" * 80)
        
        try:
            loading_result = load_data(transformation_result, destinations=load_destinations, output_dir=output_dir)
            pipeline_result["steps"]["loading"] = {
                "status": loading_result.get("status"),
                "records_loaded": loading_result.get("total_records_loaded"),
                "destinations": loading_result.get("destinations", []),
                "output_directory": output_dir
            }
            logger.info(f"✅ Loading complete: {loading_result['total_records_loaded']} records loaded")
            logger.info(f"   Destinations: {', '.join(load_destinations)}")
            logger.info(f"   Output directory: {output_dir}")
            
        except Exception as e:
            logger.error(f"❌ Loading failed: {str(e)}")
            pipeline_result["steps"]["loading"] = {
                "status": "failed",
                "error": str(e)
            }
            pipeline_result["status"] = "failed"
            pipeline_result["error"] = f"Loading error: {str(e)}"
            raise
        
        # ─────────────────────────────────────────────────────────────────────────
        # PIPELINE SUCCESS
        # ─────────────────────────────────────────────────────────────────────────
        pipeline_result["status"] = "success"
        pipeline_result["total_records"] = len(transformation_result.get("data", []))
        pipeline_result["end_time"] = datetime.utcnow().isoformat()
        
        pipeline_result["summary"] = {
            "input_file": input_file,
            "output_directory": output_dir,
            "total_records_processed": pipeline_result["total_records"],
            "extraction_status": pipeline_result["steps"]["extraction"]["status"],
            "transformation_status": pipeline_result["steps"]["transformation"]["status"],
            "loading_status": pipeline_result["steps"]["loading"]["status"],
            "load_destinations": load_destinations
        }
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ PIPELINE EXECUTION SUCCESSFUL")
        logger.info("=" * 80)
        logger.info(f"Total records processed: {pipeline_result['total_records']}")
        logger.info(f"Output directory: {output_dir}")
        logger.info("=" * 80 + "\n")
        
        return pipeline_result
        
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("❌ PIPELINE EXECUTION FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}")
        logger.error("=" * 80 + "\n")
        
        pipeline_result["status"] = "failed"
        pipeline_result["error"] = str(e)
        pipeline_result["end_time"] = datetime.utcnow().isoformat()
        
        return pipeline_result

