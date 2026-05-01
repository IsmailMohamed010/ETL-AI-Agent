"""
app/summarizer.py
Uses the local Ollama LLM to generate human-readable summaries of DB tables.
These summaries are embedded into the vector store so users can ask
"what data do we have?" and get meaningful answers.
"""
 
import logging
from app.llm import get_llm
from app.metadata import get_table_metadata, metadata_to_text
 
logger = logging.getLogger(__name__)
 
SUMMARIZE_PROMPT = """You are a data analyst assistant.
Below is the schema and sample data for a database table.
Write a clear, concise summary (3-5 sentences) describing:
- What this table contains
- What the key columns represent
- Any notable patterns from the sample data
 
Table information:
{table_info}
 
Summary:"""
 
 
def summarize_table(table_name: str) -> str:
    """
    Generates a natural language summary of a table using the LLM.
    Falls back to the raw metadata text if LLM fails.
    """
    try:
        meta = get_table_metadata(table_name)
        table_info = metadata_to_text(meta)
 
        llm = get_llm()
        prompt = SUMMARIZE_PROMPT.format(table_info=table_info)
        response = llm.invoke(prompt)
 
        # Handle both string and AIMessage responses
        if hasattr(response, "content"):
            summary = response.content
        else:
            summary = str(response)
 
        logger.info(f"Summary generated for '{table_name}'.")
        return summary.strip()
 
    except Exception as e:
        logger.warning(f"LLM summarization failed for '{table_name}': {e}. Using metadata text.")
        meta = get_table_metadata(table_name)
        return metadata_to_text(meta)
 
 
def summarize_all_tables() -> dict[str, str]:
    """Returns {table_name: summary} for all tables."""
    from app.db import get_all_tables
    tables = get_all_tables()
    summaries = {}
    for table in tables:
        summaries[table] = summarize_table(table)
    return summaries
 