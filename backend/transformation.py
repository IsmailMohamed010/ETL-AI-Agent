"""
Transformation Module for ETL Pipeline
========================================
Handles data cleaning, validation, and transformation.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class DataTransformer:
    """Transform and clean data."""
    
    @staticmethod
    def clean_data(data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Clean data by removing null values and standardizing formats.
        
        Args:
            data: List of records
            
        Returns:
            Dictionary with cleaned data
        """
        logger.info(f"[TRANSFORM] Starting data cleaning for {len(data)} records")
        
        cleaned_records = []
        cleaning_report = {
            "original_count": len(data),
            "cleaned_count": 0,
            "removed_records": 0,
            "transformations": []
        }
        
        for idx, record in enumerate(data):
            cleaned_record = {}
            
            for key, value in record.items():
                # Skip None and empty values
                if value is None or value == "":
                    continue
                
                # Convert string representations to proper types
                try:
                    if isinstance(value, str):
                        # Try to convert to number if possible
                        if value.replace(".", "").replace("-", "").isdigit():
                            if "." in value:
                                cleaned_record[key] = float(value)
                            else:
                                cleaned_record[key] = int(value)
                        else:
                            cleaned_record[key] = str(value).strip()
                    else:
                        cleaned_record[key] = value
                except Exception as e:
                    logger.warning(f"[TRANSFORM] Could not convert value {value}: {str(e)}")
                    cleaned_record[key] = value
            
            # Only add records that have at least one field
            if cleaned_record:
                cleaned_records.append(cleaned_record)
            else:
                cleaning_report["removed_records"] += 1
        
        cleaning_report["cleaned_count"] = len(cleaned_records)
        cleaning_report["transformations"].append(f"Removed {cleaning_report['removed_records']} empty records")
        
        logger.info(f"[TRANSFORM] ✅ Data cleaning complete: {len(cleaned_records)} records (removed {cleaning_report['removed_records']})")
        
        return {
            "data": cleaned_records,
            "report": cleaning_report
        }
    
    @staticmethod
    def standardize_columns(data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Standardize column names and data types.
        
        Args:
            data: List of records
            
        Returns:
            Dictionary with standardized data
        """
        logger.info(f"[TRANSFORM] Starting column standardization")
        
        standardized_records = []
        column_mapping = {}
        
        for record in data:
            standardized_record = {}
            
            for key, value in record.items():
                # Convert column names to lowercase with underscores
                new_key = key.lower().replace(" ", "_").replace("-", "_")
                
                if key != new_key:
                    column_mapping[key] = new_key
                
                standardized_record[new_key] = value
            
            standardized_records.append(standardized_record)
        
        logger.info(f"[TRANSFORM] ✅ Column standardization complete: {len(column_mapping)} columns renamed")
        
        return {
            "data": standardized_records,
            "column_mapping": column_mapping,
            "standardized_columns": list(set(list(standardized_records[0].keys()) if standardized_records else []))
        }
    
    @staticmethod
    def detect_and_remove_duplicates(data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect and remove duplicate records.
        
        Args:
            data: List of records
            
        Returns:
            Dictionary with unique records
        """
        logger.info(f"[TRANSFORM] Starting duplicate detection")
        
        unique_records = []
        seen = set()
        duplicates_found = 0
        
        for record in data:
            # Create a hashable representation of the record
            record_hash = str(sorted(record.items()))
            
            if record_hash not in seen:
                unique_records.append(record)
                seen.add(record_hash)
            else:
                duplicates_found += 1
        
        logger.info(f"[TRANSFORM] ✅ Duplicate detection complete: {duplicates_found} duplicates removed")
        
        return {
            "data": unique_records,
            "duplicates_found": duplicates_found,
            "unique_count": len(unique_records),
            "removal_rate": round((duplicates_found / len(data)) * 100, 2) if data else 0
        }
    
    @staticmethod
    def enrich_data(data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Enrich data with metadata and timestamps.
        
        Args:
            data: List of records
            
        Returns:
            Dictionary with enriched data
        """
        logger.info(f"[TRANSFORM] Starting data enrichment")
        
        enriched_records = []
        
        for idx, record in enumerate(data):
            enriched_record = record.copy()
            enriched_record["_id"] = idx + 1
            enriched_record["_processed_at"] = datetime.utcnow().isoformat()
            enriched_record["_source"] = "etl_pipeline"
            enriched_records.append(enriched_record)
        
        logger.info(f"[TRANSFORM] ✅ Data enrichment complete: added metadata to {len(enriched_records)} records")
        
        return {
            "data": enriched_records,
            "enrichment_fields": ["_id", "_processed_at", "_source"],
            "total_records": len(enriched_records)
        }
    
    @staticmethod
    def validate_data(data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate data quality and consistency.
        
        Args:
            data: List of records
            
        Returns:
            Validation report
        """
        logger.info(f"[TRANSFORM] Starting data validation")
        
        validation_report = {
            "total_records": len(data),
            "valid_records": 0,
            "invalid_records": 0,
            "issues": [],
            "data_types": {}
        }
        
        for idx, record in enumerate(data):
            if not record or len(record) == 0:
                validation_report["invalid_records"] += 1
                validation_report["issues"].append(f"Record {idx}: Empty record")
            else:
                validation_report["valid_records"] += 1
        
        # Detect data types
        if data:
            for key in data[0].keys():
                types_set = set()
                for record in data:
                    if key in record:
                        types_set.add(type(record[key]).__name__)
                validation_report["data_types"][key] = list(types_set)
        
        logger.info(f"[TRANSFORM] ✅ Data validation complete: {validation_report['valid_records']} valid, {validation_report['invalid_records']} invalid")
        
        return validation_report


def transform_data(data: Dict[str, Any], transform_type: str = "full") -> Dict[str, Any]:
    """
    Main transformation function.
    
    Args:
        data: Extracted data
        transform_type: Type of transformation ("full", "clean", "standardize", etc.)
        
    Returns:
        Transformed data
    """
    logger.info(f"[TRANSFORM] transform_data called with type: {transform_type}")
    
    records = data.get("data", [])
    
    if not records:
        logger.warning("[TRANSFORM] No data to transform")
        return {"data": [], "transforms_applied": []}
    
    result = {
        "data": records,
        "transforms_applied": [],
        "original_count": len(records),
        "final_count": len(records)
    }
    
    try:
        if transform_type in ["full", "clean"]:
            # Step 1: Clean data
            cleaned = DataTransformer.clean_data(records)
            records = cleaned["data"]
            result["transforms_applied"].append("data_cleaning")
            result["cleaning_report"] = cleaned.get("report")
        
        if transform_type in ["full", "standardize"]:
            # Step 2: Standardize columns
            standardized = DataTransformer.standardize_columns(records)
            records = standardized["data"]
            result["transforms_applied"].append("column_standardization")
            result["column_mapping"] = standardized.get("column_mapping")
        
        if transform_type in ["full"]:
            # Step 3: Remove duplicates
            deduped = DataTransformer.detect_and_remove_duplicates(records)
            records = deduped["data"]
            result["transforms_applied"].append("duplicate_removal")
            result["duplicates_removed"] = deduped.get("duplicates_found")
            
            # Step 4: Enrich data
            enriched = DataTransformer.enrich_data(records)
            records = enriched["data"]
            result["transforms_applied"].append("data_enrichment")
            
            # Step 5: Validate
            validation = DataTransformer.validate_data(records)
            result["validation_report"] = validation
            result["transforms_applied"].append("data_validation")
        
        result["data"] = records
        result["final_count"] = len(records)
        
        logger.info(f"[TRANSFORM] ✅ Transformation complete: {result['final_count']} records after {len(result['transforms_applied'])} transformations")
        
    except Exception as e:
        logger.error(f"[TRANSFORM] ❌ Transformation error: {str(e)}")
        raise
    
    return result
