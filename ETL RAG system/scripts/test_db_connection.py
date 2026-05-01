"""
scripts/test_db_connection.py
Tests the SQL Server connection and prints available tables.
Usage: python -m scripts.test_db_connection
"""
 
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
 
from app.db import test_connection, get_all_tables, fetch_table_as_df
from app.config import DB_SERVER, DB_NAME
 
if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"Testing connection to: {DB_SERVER} / {DB_NAME}")
    print(f"{'='*50}\n")
 
    ok = test_connection()
    if not ok:
        print("❌ Connection failed. Check your .env file.")
        exit(1)
 
    tables = get_all_tables()
    print(f"\nFound {len(tables)} tables:")
    for t in tables:
        try:
            df = fetch_table_as_df(t, limit=1)
            cols = list(df.columns)
            print(f"  • {t} — columns: {cols}")
        except Exception as e:
            print(f"  • {t} — ⚠️ Could not read: {e}")
 
    print(f"\n✅ Connection test complete.")
 