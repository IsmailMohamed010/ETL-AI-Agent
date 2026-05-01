"""
app/metadata.py
Extracts and formats table schema metadata from SQL Server.
Used to give the LLM context about what data is available.
"""
 
import logging
from app.db import get_all_tables, get_table_columns, fetch_table_as_df
 
logger = logging.getLogger(__name__)
 
 
def get_table_metadata(table_name: str) -> dict:
    """
    Returns a dict describing a table:
    {
        "table": str,
        "columns": [{"name": str, "type": str}, ...],
        "row_count": int,
        "sample": list[dict]   # first 3 rows
    }
    """
    columns = get_table_columns(table_name)
    df = fetch_table_as_df(table_name, limit=3)
    row_count_df = fetch_table_as_df(table_name, limit=1)
 
    # Get actual row count
    from app.db import run_sql_query
    try:
        count_df = run_sql_query(f"SELECT COUNT(*) AS cnt FROM [{table_name}]")
        row_count = int(count_df["cnt"].iloc[0])
    except Exception:
        row_count = -1
 
    sample = df.to_dict("records") if not df.empty else []
 
    return {
        "table": table_name,
        "columns": columns,
        "row_count": row_count,
        "sample": sample,
    }
 
 
def get_all_metadata() -> list[dict]:
    """Returns metadata for all tables in the database."""
    tables = get_all_tables()
    meta = []
    for t in tables:
        try:
            m = get_table_metadata(t)
            meta.append(m)
        except Exception as e:
            logger.warning(f"Could not get metadata for '{t}': {e}")
    return meta
 
 
def metadata_to_text(meta: dict) -> str:
    """
    Converts a table metadata dict into a plain-text description
    suitable for embedding into the vector store.
    """
    lines = [f"Table: {meta['table']}"]
    lines.append(f"Row count: {meta['row_count']}")
    lines.append("Columns:")
    for col in meta.get("columns", []):
        lines.append(f"  - {col['name']} ({col['type']})")
 
    if meta.get("sample"):
        lines.append("Sample rows:")
        for row in meta["sample"][:3]:
            row_str = ", ".join(f"{k}={v}" for k, v in row.items())
            lines.append(f"  {{ {row_str} }}")
 
    return "\n".join(lines)
 
 
def all_tables_summary_text() -> str:
    """
    Returns a combined text of all table metadata.
    Used as context for the LLM router/profiler.
    """
    all_meta = get_all_metadata()
    if not all_meta:
        return "No tables found in the database."
    parts = [metadata_to_text(m) for m in all_meta]
    return "\n\n" + ("=" * 40) + "\n\n".join(parts)
 