"""
app/views.py
Creates SQL views in the database to simplify querying.
Views are auto-generated from existing tables (e.g., a unified "all_data" view).
"""
 
import logging
from app.db import get_connection, get_all_tables, get_table_columns
 
logger = logging.getLogger(__name__)
 
 
def create_view(view_name: str, sql_definition: str) -> bool:
    """
    Creates or replaces a SQL view.
 
    Args:
        view_name:      Name of the view to create.
        sql_definition: The SELECT statement that defines the view.
 
    Returns:
        True if successful, False otherwise.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Drop if exists first (SQL Server doesn't support CREATE OR REPLACE VIEW)
        cursor.execute(f"""
            IF OBJECT_ID('{view_name}', 'V') IS NOT NULL
                DROP VIEW [{view_name}]
        """)
        cursor.execute(f"CREATE VIEW [{view_name}] AS {sql_definition}")
        conn.commit()
        conn.close()
        logger.info(f"View '{view_name}' created successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to create view '{view_name}': {e}")
        return False
 
 
def create_table_summary_view() -> bool:
    """
    Creates a meta-view 'vw_table_summary' that shows all tables with row counts.
    Useful for the LLM to quickly understand available data.
    """
    tables = get_all_tables()
    if not tables:
        logger.warning("No tables found, skipping summary view creation.")
        return False
 
    union_parts = []
    for table in tables:
        union_parts.append(
            f"SELECT '{table}' AS table_name, COUNT(*) AS row_count FROM [{table}]"
        )
 
    sql = " UNION ALL ".join(union_parts)
    return create_view("vw_table_summary", sql)
 
 
def create_all_views() -> dict[str, bool]:
    """
    Creates all standard views. Returns {view_name: success}.
    Add more view creators here as needed.
    """
    results = {}
    results["vw_table_summary"] = create_table_summary_view()
    return results
 
 
def list_views() -> list[str]:
    """Returns all view names in the current database."""
    from app.db import run_sql_query
    try:
        df = run_sql_query("""
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.VIEWS
            ORDER BY TABLE_NAME
        """)
        return df["TABLE_NAME"].tolist()
    except Exception as e:
        logger.error(f"Could not list views: {e}")
        return []
 