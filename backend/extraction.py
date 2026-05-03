"""
Extraction Module for ETL Pipeline
====================================
Handles data extraction from various sources (files, databases, web).
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


class DataExtractor:
    """Extract data from various sources."""
    
    @staticmethod
    def extract_from_file(file_path: str) -> Dict[str, Any]:
        """
        Extract data from CSV or Excel files.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with extracted data
        """
        logger.info(f"[EXTRACT] Starting extraction from file: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"[EXTRACT] File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_ext = Path(file_path).suffix.lower()
        extracted_data = {
            "source": "file",
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "extraction_time": datetime.utcnow().isoformat(),
            "data": {},
            "metadata": {}
        }
        
        try:
            if file_ext == ".csv":
                logger.info(f"[EXTRACT] Reading CSV file: {file_path}")
                df = pd.read_csv(file_path)
                extracted_data["data"] = df.to_dict(orient="records")
                extracted_data["metadata"] = {
                    "format": "csv",
                    "rows": len(df),
                    "columns": list(df.columns),
                    "dtypes": df.dtypes.astype(str).to_dict()
                }
                logger.info(f"[EXTRACT] ✅ CSV extraction complete: {len(df)} rows, {len(df.columns)} columns")
                
            elif file_ext in [".xlsx", ".xls"]:
                logger.info(f"[EXTRACT] Reading Excel file: {file_path}")
                sheets = pd.read_excel(file_path, sheet_name=None)
                
                all_data = []
                sheet_info = {}
                
                for sheet_name, df in sheets.items():
                    sheet_data = df.to_dict(orient="records")
                    all_data.extend(sheet_data)
                    sheet_info[sheet_name] = {
                        "rows": len(df),
                        "columns": list(df.columns),
                    }
                
                extracted_data["data"] = all_data
                extracted_data["metadata"] = {
                    "format": "excel",
                    "total_rows": len(all_data),
                    "sheets": sheet_info,
                    "sheet_count": len(sheets)
                }
                logger.info(f"[EXTRACT] ✅ Excel extraction complete: {len(all_data)} rows from {len(sheets)} sheets")
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
                
        except Exception as e:
            logger.error(f"[EXTRACT] ❌ Error extracting data: {str(e)}")
            extracted_data["error"] = str(e)
            raise
        
        return extracted_data
    
    @staticmethod
    def extract_multiple_files(file_paths: List[str]) -> Dict[str, Any]:
        """
        Extract data from multiple files.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Combined extracted data
        """
        logger.info(f"[EXTRACT] Starting extraction from {len(file_paths)} files")
        
        combined_data = {
            "source": "files",
            "files_count": len(file_paths),
            "extraction_time": datetime.utcnow().isoformat(),
            "data": [],
            "metadata": {}
        }
        
        for file_path in file_paths:
            try:
                file_data = DataExtractor.extract_from_file(file_path)
                combined_data["data"].extend(file_data.get("data", []))
            except Exception as e:
                logger.warning(f"[EXTRACT] Skipping file {file_path}: {str(e)}")
                continue
        
        combined_data["metadata"] = {
            "total_files_processed": len(file_paths),
            "total_records": len(combined_data["data"])
        }
        
        logger.info(f"[EXTRACT] ✅ Multi-file extraction complete: {len(combined_data['data'])} total records")
        return combined_data
    
    @staticmethod
    def detect_data_issues(data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect common data quality issues.
        
        Args:
            data: List of records
            
        Returns:
            Dictionary with detected issues
        """
        logger.info(f"[EXTRACT] Analyzing data quality for {len(data)} records")
        
        issues = {
            "missing_values": {},
            "duplicate_rows": 0,
            "empty_columns": [],
            "data_type_mismatches": []
        }
        
        if not data:
            logger.warning("[EXTRACT] No data to analyze")
            return issues
        
        # Detect missing values
        for key in data[0].keys():
            missing_count = sum(1 for record in data if record.get(key) is None or record.get(key) == "")
            if missing_count > 0:
                issues["missing_values"][key] = {
                    "count": missing_count,
                    "percentage": round((missing_count / len(data)) * 100, 2)
                }
        
        # Detect duplicate rows
        unique_records = len(set(str(record) for record in data))
        issues["duplicate_rows"] = len(data) - unique_records
        
        logger.info(f"[EXTRACT] ✅ Data quality analysis complete: {len(issues['missing_values'])} columns with missing values, {issues['duplicate_rows']} duplicates")
        return issues


def extract_data(source: str, **kwargs) -> Dict[str, Any]:
    """
    Main extraction function.
    
    Args:
        source: "file" or "files"
        **kwargs: Additional arguments (file_path or file_paths)
        
    Returns:
        Extracted data
    """
    logger.info(f"[EXTRACT] extract_data called with source: {source}")
    
    if source == "file":
        file_path = kwargs.get("file_path")
        if not file_path:
            raise ValueError("file_path required for file extraction")
        return DataExtractor.extract_from_file(file_path)
    
    elif source == "files":
        file_paths = kwargs.get("file_paths")
        if not file_paths:
            raise ValueError("file_paths required for multi-file extraction")
        return DataExtractor.extract_multiple_files(file_paths)
    
    else:
        raise ValueError(f"Unknown extraction source: {source}")
