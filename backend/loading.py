"""
Loading Module for ETL Pipeline
=================================
Handles data loading to various destinations (CSV, Database, JSON).
"""

import logging
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import sqlite3

logger = logging.getLogger(__name__)


class DataLoader:
    """Load data to various destinations."""
    
    @staticmethod
    def save_to_csv(data: List[Dict[str, Any]], file_path: str, overwrite: bool = True) -> Dict[str, Any]:
        """
        Save data to CSV file.
        
        Args:
            data: List of records
            file_path: Path to save CSV
            overwrite: Whether to overwrite existing file
            
        Returns:
            Loading report
        """
        logger.info(f"[LOAD] Saving {len(data)} records to CSV: {file_path}")
        
        if not overwrite and os.path.exists(file_path):
            logger.warning(f"[LOAD] File already exists and overwrite is False: {file_path}")
            return {"status": "skipped", "reason": "File exists and overwrite=False"}
        
        try:
            # Create directory if it doesn't exist
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to DataFrame and save
            df = pd.DataFrame(data)
            df.to_csv(file_path, index=False)
            
            file_size = os.path.getsize(file_path)
            logger.info(f"[LOAD] ✅ CSV saved successfully: {file_path} ({file_size} bytes)")
            
            return {
                "status": "success",
                "destination": "csv",
                "file_path": file_path,
                "records_saved": len(data),
                "file_size": file_size,
                "saved_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"[LOAD] ❌ Error saving CSV: {str(e)}")
            raise
    
    @staticmethod
    def save_to_json(data: List[Dict[str, Any]], file_path: str, pretty: bool = True) -> Dict[str, Any]:
        """
        Save data to JSON file.
        
        Args:
            data: List of records
            file_path: Path to save JSON
            pretty: Whether to pretty-print JSON
            
        Returns:
            Loading report
        """
        logger.info(f"[LOAD] Saving {len(data)} records to JSON: {file_path}")
        
        try:
            # Create directory if it doesn't exist
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w") as f:
                if pretty:
                    json.dump(data, f, indent=2, default=str)
                else:
                    json.dump(data, f, default=str)
            
            file_size = os.path.getsize(file_path)
            logger.info(f"[LOAD] ✅ JSON saved successfully: {file_path} ({file_size} bytes)")
            
            return {
                "status": "success",
                "destination": "json",
                "file_path": file_path,
                "records_saved": len(data),
                "file_size": file_size,
                "saved_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"[LOAD] ❌ Error saving JSON: {str(e)}")
            raise
    
    @staticmethod
    def save_to_sqlite(data: List[Dict[str, Any]], db_path: str, table_name: str = "data") -> Dict[str, Any]:
        """
        Save data to SQLite database.
        
        Args:
            data: List of records
            db_path: Path to SQLite database
            table_name: Name of the table to create
            
        Returns:
            Loading report
        """
        logger.info(f"[LOAD] Saving {len(data)} records to SQLite: {db_path} (table: {table_name})")
        
        try:
            # Create directory if it doesn't exist
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Create DataFrame and save to SQLite
            df = pd.DataFrame(data)
            
            conn = sqlite3.connect(db_path)
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            conn.commit()
            conn.close()
            
            file_size = os.path.getsize(db_path)
            logger.info(f"[LOAD] ✅ SQLite saved successfully: {db_path} ({file_size} bytes)")
            
            return {
                "status": "success",
                "destination": "sqlite",
                "db_path": db_path,
                "table_name": table_name,
                "records_saved": len(data),
                "file_size": file_size,
                "saved_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"[LOAD] ❌ Error saving to SQLite: {str(e)}")
            raise
    
    @staticmethod
    def create_summary_report(data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a summary report of the data.
        
        Args:
            data: List of records
            
        Returns:
            Summary report
        """
        logger.info(f"[LOAD] Creating summary report for {len(data)} records")
        
        report = {
            "total_records": len(data),
            "total_fields": len(data[0].keys()) if data else 0,
            "fields": list(data[0].keys()) if data else [],
            "sample_record": data[0] if data else None,
            "record_samples": data[:5] if len(data) > 5 else data
        }
        
        logger.info(f"[LOAD] ✅ Summary report created")
        return report


def load_data(data: Dict[str, Any], destinations: Optional[List[str]] = None, output_dir: str = "output") -> Dict[str, Any]:
    """
    Main loading function.
    
    Args:
        data: Transformed data from transformation step
        destinations: List of destinations ("csv", "json", "sqlite", "all")
        output_dir: Directory to save output files
        
    Returns:
        Loading report
    """
    logger.info(f"[LOAD] load_data called with destinations: {destinations}")
    
    if destinations is None:
        destinations = ["csv", "json"]
    
    if "all" in destinations:
        destinations = ["csv", "json", "sqlite"]
    
    records = data.get("data", [])
    
    if not records:
        logger.warning("[LOAD] No data to load")
        return {"status": "skipped", "reason": "No data to load"}
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    loading_report = {
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "total_records_loaded": len(records),
        "destinations": [],
        "summary": DataLoader.create_summary_report(records)
    }
    
    try:
        # Load to CSV
        if "csv" in destinations:
            csv_path = os.path.join(output_dir, "data_output.csv")
            result = DataLoader.save_to_csv(records, csv_path)
            loading_report["destinations"].append(result)
            logger.info(f"[LOAD] CSV destination result: {result['status']}")
        
        # Load to JSON
        if "json" in destinations:
            json_path = os.path.join(output_dir, "data_output.json")
            result = DataLoader.save_to_json(records, json_path)
            loading_report["destinations"].append(result)
            logger.info(f"[LOAD] JSON destination result: {result['status']}")
        
        # Load to SQLite
        if "sqlite" in destinations:
            db_path = os.path.join(output_dir, "data_output.db")
            result = DataLoader.save_to_sqlite(records, db_path, table_name="extracted_data")
            loading_report["destinations"].append(result)
            logger.info(f"[LOAD] SQLite destination result: {result['status']}")
        
        logger.info(f"[LOAD] ✅ Loading complete: {len(loading_report['destinations'])} destinations")
        
    except Exception as e:
        logger.error(f"[LOAD] ❌ Loading error: {str(e)}")
        loading_report["status"] = "failed"
        loading_report["error"] = str(e)
        raise
    
    return loading_report
