"""
app/profiler.py
Generates a high-level profile of all tables in the database.
Used when the user asks "what data do we have?" or similar overview questions.
"""
 
import logging
from app.metadata import get_all_metadata, metadata_to_text
from app.llm import get_llm
 
logger = logging.getLogger(__name__)
 
PROFILE_PROMPT = """You are a data analyst assistant.
Below is the schema and metadata for all tables in our database.
Write a clear, structured overview that helps a business user understand:
1. What datasets are available
2. What each table contains
3. How many records each table has
4. Any obvious relationships between tables
 
Database metadata:
{metadata}
 
Overview:"""
 
 
def profile_database() -> str:
    """
    Returns a natural-language profile of the entire database.
    Uses the LLM if available, falls back to raw metadata text.
    """
    all_meta = get_all_metadata()
 
    if not all_meta:
        return "No tables found in the database."
 
    combined = "\n\n".join(metadata_to_text(m) for m in all_meta)
 
    try:
        llm = get_llm()
        prompt = PROFILE_PROMPT.format(metadata=combined)
        response = llm.invoke(prompt)
        if hasattr(response, "content"):
            return response.content.strip()
        return str(response).strip()
    except Exception as e:
        logger.warning(f"LLM profiling failed: {e}. Returning raw metadata.")
        lines = [f"Database contains {len(all_meta)} table(s):\n"]
        for m in all_meta:
            lines.append(metadata_to_text(m))
            lines.append("")
        return "\n".join(lines)
 
 
def quick_stats() -> dict:
    """
    Returns a quick summary dict: {table_name: row_count}.
    """
    all_meta = get_all_metadata()
    return {m["table"]: m["row_count"] for m in all_meta}