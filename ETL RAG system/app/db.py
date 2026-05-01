"""
app/db.py
SQL Server connection, table discovery, and data fetching utilities.
Uses SQLAlchemy to avoid pandas warnings.
"""
 
import logging
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
 
from app.config import DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD, DB_DRIVER
 
logger = logging.getLogger(__name__)
 
 
def _get_engine():
    if DB_USER and DB_PASSWORD:
        conn_str = (
            f"DRIVER={{{DB_DRIVER}}};"
            f"SERVER={DB_SERVER};"
            f"DATABASE={DB_NAME};"
            f"UID={DB_USER};"
            f"PWD={DB_PASSWORD};"
        )
    else:
        conn_str = (
            f"DRIVER={{{DB_DRIVER}}};"
            f"SERVER={DB_SERVER};"
            f"DATABASE={DB_NAME};"
            f"Trusted_Connection=yes;"
        )
    connection_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"
    return create_engine(connection_url, fast_executemany=True)
 
 
def test_connection() -> bool:
    """Returns True if connection succeeds."""
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("DB connection successful.")
        return True
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
        return False
 
 
def get_all_tables() -> list[str]:
    """Returns all user table names in the current database."""
    query = """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """
    try:
        engine = _get_engine()
        df = pd.read_sql(query, engine)
        return df["TABLE_NAME"].tolist()
    except Exception as e:
        logger.error(f"Could not fetch tables: {e}")
        return []
 
 
def get_table_columns(table_name: str) -> list[dict]:
    """Returns list of {name, type} for each column in the table."""
    query = f"""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{table_name}'
        ORDER BY ORDINAL_POSITION
    """
    try:
        engine = _get_engine()
        df = pd.read_sql(query, engine)
        return df.rename(columns={"COLUMN_NAME": "name", "DATA_TYPE": "type"}).to_dict("records")
    except Exception as e:
        logger.error(f"Could not fetch columns for {table_name}: {e}")
        return []
 
 
def fetch_table_as_df(table_name: str, limit: int = 500) -> pd.DataFrame:
    """Fetches rows from a table as a DataFrame."""
    query = f"SELECT TOP {limit} * FROM [{table_name}]"
    try:
        engine = _get_engine()
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        logger.error(f"Could not fetch data from {table_name}: {e}")
        return pd.DataFrame()
 
 
def run_sql_query(sql: str) -> pd.DataFrame:
    """Runs a raw SQL query and returns results as DataFrame."""
    try:
        engine = _get_engine()
        df = pd.read_sql(sql, engine)
        return df
    except Exception as e:
        logger.error(f"SQL query failed: {e}")
        raise