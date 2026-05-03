"""
Test Suite for ETL Pipeline
=============================
Direct testing of the run_etl_pipeline function without needing the web server.

Run with:
    python test_pipeline.py
"""

import os
import sys
import json
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from processing import run_etl_pipeline
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_data():
    """Create sample data for testing."""
    logger.info("Creating sample CSV file for testing...")
    
    # Create sample data
    data = {
        "ID": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "Name": ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Henry", "Ivy", "Jack"],
        "Department": ["Sales", "IT", "HR", "Sales", "IT", "HR", "Sales", "IT", "HR", "Sales"],
        "Salary": [50000, 60000, 55000, 52000, 62000, 58000, 51000, 65000, 57000, 53000],
        "Email": [
            "alice@example.com",
            "bob@example.com",
            "charlie@example.com",
            "david@example.com",
            "eve@example.com",
            "frank@example.com",
            "grace@example.com",
            "henry@example.com",
            "ivy@example.com",
            "jack@example.com"
        ]
    }
    
    df = pd.DataFrame(data)
    sample_file = "sample_data.csv"
    df.to_csv(sample_file, index=False)
    
    logger.info(f"✅ Sample data created: {sample_file}")
    return sample_file


def test_basic_pipeline():
    """Test 1: Basic pipeline execution."""
    print("\n" + "=" * 80)
    print("TEST 1: Basic ETL Pipeline Execution")
    print("=" * 80)
    
    try:
        # Create sample data
        input_file = create_sample_data()
        
        # Run pipeline
        logger.info("\n🚀 Running ETL pipeline...")
        result = run_etl_pipeline(
            input_file=input_file,
            output_dir="test_output_1",
            load_destinations=["csv", "json", "sqlite"],
            transform_type="full"
        )
        
        # Check results
        assert result["status"] == "success", f"Pipeline failed: {result.get('error')}"
        assert result["total_records"] > 0, "No records processed"
        assert result["steps"]["extraction"]["status"] == "success", "Extraction failed"
        assert result["steps"]["transformation"]["status"] == "success", "Transformation failed"
        assert result["steps"]["loading"]["status"] == "success", "Loading failed"
        
        print("\n✅ TEST 1 PASSED: Basic pipeline works correctly")
        print(f"   - Records processed: {result['total_records']}")
        print(f"   - Output directory: {result['summary']['output_directory']}")
        print(f"   - Loaded to: {', '.join(result['summary']['load_destinations'])}")
        
        # Verify output files exist
        output_dir = result['summary']['output_directory']
        assert os.path.exists(os.path.join(output_dir, "data_output.csv")), "CSV file not created"
        assert os.path.exists(os.path.join(output_dir, "data_output.json")), "JSON file not created"
        assert os.path.exists(os.path.join(output_dir, "data_output.db")), "SQLite file not created"
        
        print("   - All output files verified ✅")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {str(e)}")
        return False


def test_clean_transformation():
    """Test 2: Pipeline with clean transformation only."""
    print("\n" + "=" * 80)
    print("TEST 2: Pipeline with Clean Transformation")
    print("=" * 80)
    
    try:
        # Create sample data with some issues
        logger.info("Creating sample data with data quality issues...")
        
        data = {
            "ID": [1, 2, None, 4, 5],
            "Name": ["Alice", "Bob", "", "David", "Eve"],
            "Score": ["100", "95", "88", None, "92"]
        }
        
        df = pd.DataFrame(data)
        input_file = "sample_with_issues.csv"
        df.to_csv(input_file, index=False)
        
        # Run pipeline with clean transformation
        logger.info("\n🚀 Running pipeline with clean transformation...")
        result = run_etl_pipeline(
            input_file=input_file,
            output_dir="test_output_2",
            load_destinations=["csv"],
            transform_type="clean"
        )
        
        # Check results
        assert result["status"] == "success", f"Pipeline failed: {result.get('error')}"
        assert result["steps"]["transformation"]["status"] == "success", "Transformation failed"
        
        cleaning_report = result["steps"]["transformation"]["details"].get("cleaning_report", {})
        print("\n✅ TEST 2 PASSED: Clean transformation works")
        print(f"   - Original records: {cleaning_report.get('original_count')}")
        print(f"   - Cleaned records: {cleaning_report.get('cleaned_count')}")
        print(f"   - Records removed: {cleaning_report.get('removed_records')}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {str(e)}")
        return False


def test_csv_only():
    """Test 3: Pipeline loading to CSV only."""
    print("\n" + "=" * 80)
    print("TEST 3: Pipeline with CSV-only Output")
    print("=" * 80)
    
    try:
        input_file = create_sample_data()
        
        logger.info("\n🚀 Running pipeline with CSV-only output...")
        result = run_etl_pipeline(
            input_file=input_file,
            output_dir="test_output_3",
            load_destinations=["csv"],
            transform_type="full"
        )
        
        assert result["status"] == "success", f"Pipeline failed: {result.get('error')}"
        
        # Verify only CSV was created
        output_dir = result['summary']['output_directory']
        assert os.path.exists(os.path.join(output_dir, "data_output.csv")), "CSV file not created"
        assert not os.path.exists(os.path.join(output_dir, "data_output.json")), "JSON should not exist"
        assert not os.path.exists(os.path.join(output_dir, "data_output.db")), "DB should not exist"
        
        print("\n✅ TEST 3 PASSED: CSV-only loading works correctly")
        print(f"   - Output file: data_output.csv")
        print(f"   - Records saved: {result['total_records']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED: {str(e)}")
        return False


def test_error_handling():
    """Test 4: Error handling for missing file."""
    print("\n" + "=" * 80)
    print("TEST 4: Error Handling - Missing File")
    print("=" * 80)
    
    try:
        logger.info("\n🚀 Running pipeline with non-existent file...")
        result = run_etl_pipeline(
            input_file="non_existent_file.csv",
            output_dir="test_output_4",
            load_destinations=["csv"]
        )
        
        # Should fail gracefully
        assert result["status"] == "failed", "Should have failed with missing file"
        assert result["error"] is not None, "Should have error message"
        
        print("\n✅ TEST 4 PASSED: Error handling works correctly")
        print(f"   - Error message: {result['error']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 4 FAILED: {str(e)}")
        return False


def test_pipeline_with_excel():
    """Test 5: Pipeline with Excel file."""
    print("\n" + "=" * 80)
    print("TEST 5: Pipeline with Excel File")
    print("=" * 80)
    
    try:
        # Create sample Excel file
        logger.info("Creating sample Excel file...")
        
        data = {
            "Product": ["A", "B", "C", "D"],
            "Quantity": [10, 20, 15, 30],
            "Price": [100, 200, 150, 300]
        }
        
        df = pd.DataFrame(data)
        excel_file = "sample_data.xlsx"
        df.to_excel(excel_file, index=False, sheet_name="Products")
        
        # Run pipeline
        logger.info("\n🚀 Running pipeline with Excel file...")
        result = run_etl_pipeline(
            input_file=excel_file,
            output_dir="test_output_5",
            load_destinations=["csv", "json"],
            transform_type="full"
        )
        
        assert result["status"] == "success", f"Pipeline failed: {result.get('error')}"
        
        print("\n✅ TEST 5 PASSED: Excel file processing works")
        print(f"   - Records processed: {result['total_records']}")
        print(f"   - File format: {result['steps']['extraction']['format']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 5 FAILED: {str(e)}")
        return False


def cleanup_test_files():
    """Clean up test files."""
    logger.info("\n🧹 Cleaning up test files...")
    
    files_to_remove = [
        "sample_data.csv",
        "sample_with_issues.csv",
        "sample_data.xlsx"
    ]
    
    for file in files_to_remove:
        if os.path.exists(file):
            os.remove(file)
            logger.info(f"Removed: {file}")
    
    # Remove test output directories
    import shutil
    for i in range(1, 6):
        test_dir = f"test_output_{i}"
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
            logger.info(f"Removed: {test_dir}")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("ETL PIPELINE TEST SUITE")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Basic Pipeline Execution", test_basic_pipeline),
        ("Clean Transformation", test_clean_transformation),
        ("CSV-Only Output", test_csv_only),
        ("Error Handling", test_error_handling),
        ("Excel File Processing", test_pipeline_with_excel)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.error(f"Test {test_name} encountered exception: {str(e)}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print("=" * 80)
    print(f"Results: {passed_count}/{total_count} tests passed")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Cleanup
    cleanup_test_files()
    
    # Return exit code
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
