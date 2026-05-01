"""
scripts/build_vector_store.py
Run this script to ingest ALL tables from the DB into the vector store.
Usage: python -m scripts.build_vector_store [--force]
"""
 
import sys
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
 
from app.agent import initialize, ingest_all_tables
 
if __name__ == "__main__":
    force = "--force" in sys.argv
    initialize()
    print(f"\n{'='*50}")
    print(f"Building vector store (force={force})...")
    print(f"{'='*50}\n")
 
    results = ingest_all_tables(force=force)
 
    print(f"\n{'='*50}")
    print("Ingestion Summary:")
    for r in results:
        status = r.get("status")
        source = r.get("source")
        rows   = r.get("rows", "-")
        chunks = r.get("chunks", "-")
        error  = r.get("error", "")
        print(f"  [{status.upper()}] {source} — rows: {rows}, chunks: {chunks} {error}")
    print(f"{'='*50}\n")
 