"""
app/agent.py
Main orchestrator — initialize the system, ingest data, and answer queries.
This is the single entry point used by all scripts.
"""
 
import logging
from app.config import MAX_ROWS_INGEST
 
logger = logging.getLogger(__name__)
 
_initialized = False
 
 
# ── Initialization ─────────────────────────────────────────────────────────────
 
def initialize() -> None:
    """
    Initializes the RAG system:
    - Loads the embedding model
    - Loads the vector store from disk (if it exists)
    Should be called once at startup.
    """
    global _initialized
    if _initialized:
        return
 
    logger.info("Initializing RAG system...")
 
    from app.embeddings import get_embeddings
    get_embeddings()  # Warms up the model
 
    from app.vector_store import load_store
    load_store()
 
    _initialized = True
    logger.info("RAG system initialized.")
 
 
# ── Ingestion ──────────────────────────────────────────────────────────────────
 
def ingest_table(table_name: str, force: bool = False) -> dict:
    """
    Ingests a single SQL table into the vector store.
 
    Args:
        table_name: Name of the table to ingest.
        force:      If True, re-ingest even if the source already exists.
 
    Returns:
        {"status": "ok"|"skipped"|"error", "source": str, "rows": int, "chunks": int, "error": str}
    """
    from app.vector_store import source_exists, add_documents
    from app.db import fetch_table_as_df
    from app.chunking import dataframe_to_documents
 
    source_name = f"table__{table_name}"
 
    if not force and source_exists(source_name):
        logger.info(f"'{table_name}' already ingested, skipping.")
        return {"status": "skipped", "source": source_name}
 
    try:
        df = fetch_table_as_df(table_name, limit=MAX_ROWS_INGEST)
        if df.empty:
            logger.warning(f"Table '{table_name}' is empty.")
            return {"status": "skipped", "source": source_name, "rows": 0, "chunks": 0}
 
        docs = dataframe_to_documents(
            df,
            source_name=source_name,
            metadata={"type": "table_data", "table": table_name},
        )
        add_documents(docs)
        return {"status": "ok", "source": source_name, "rows": len(df), "chunks": len(docs)}
 
    except Exception as e:
        logger.error(f"Ingestion failed for '{table_name}': {e}")
        return {"status": "error", "source": source_name, "error": str(e)}
 
 
def ingest_table_metadata(table_name: str, force: bool = False) -> dict:
    """
    Ingests table schema metadata (column names, types, sample rows) into the vector store.
    This helps the LLM answer "what columns does X table have?" questions.
    """
    from app.vector_store import source_exists, add_documents
    from app.metadata import get_table_metadata, metadata_to_text
    from app.chunking import text_to_documents
 
    source_name = f"metadata__{table_name}"
 
    if not force and source_exists(source_name):
        return {"status": "skipped", "source": source_name}
 
    try:
        meta = get_table_metadata(table_name)
        text = metadata_to_text(meta)
        docs = text_to_documents(
            text,
            source_name=source_name,
            metadata={"type": "metadata", "table": table_name},
        )
        from app.vector_store import add_documents
        add_documents(docs)
        return {"status": "ok", "source": source_name, "chunks": len(docs)}
    except Exception as e:
        logger.error(f"Metadata ingestion failed for '{table_name}': {e}")
        return {"status": "error", "source": source_name, "error": str(e)}
 
 
def ingest_table_summary(table_name: str, force: bool = False) -> dict:
    """
    Generates an LLM summary of a table and ingests it into the vector store.
    """
    from app.vector_store import source_exists, add_documents
    from app.summarizer import summarize_table
    from app.chunking import text_to_documents
 
    source_name = f"summary__{table_name}"
 
    if not force and source_exists(source_name):
        return {"status": "skipped", "source": source_name}
 
    try:
        summary = summarize_table(table_name)
        docs = text_to_documents(
            summary,
            source_name=source_name,
            metadata={"type": "summary", "table": table_name},
        )
        add_documents(docs)
        return {"status": "ok", "source": source_name, "chunks": len(docs)}
    except Exception as e:
        logger.error(f"Summary ingestion failed for '{table_name}': {e}")
        return {"status": "error", "source": source_name, "error": str(e)}
 
 
def ingest_all_tables(force: bool = False) -> list[dict]:
    """
    Full ingestion pipeline for all tables:
    1. Raw table data
    2. Schema metadata
    3. LLM-generated summaries
 
    Returns:
        List of result dicts from each ingestion step.
    """
    from app.db import get_all_tables
 
    tables = get_all_tables()
    if not tables:
        logger.warning("No tables found in database.")
        return []
 
    logger.info(f"Starting full ingestion for {len(tables)} tables...")
    results = []
 
    for table in tables:
        logger.info(f"Ingesting table: {table}")
        results.append(ingest_table(table, force=force))
        results.append(ingest_table_metadata(table, force=force))
        results.append(ingest_table_summary(table, force=force))
 
    logger.info("Full ingestion complete.")
    return results
 
 
# ── Query ──────────────────────────────────────────────────────────────────────
 
def query(question: str) -> dict:
    """
    Main query entry point. Routes the question and returns an answer.
 
    Args:
        question: The user's natural language question.
 
    Returns:
        {
            "answer": str,
            "route": "rag" | "sql" | "general",
            "sources": list[str]   (optional)
        }
    """
    from app.router import route_query
    from app.rag_chain import rag_answer, sql_answer
    from app.profiler import profile_database
 
    if not question or not question.strip():
        return {"answer": "Please ask a question.", "route": "general", "sources": []}
 
    route = route_query(question)
 
    if route == "sql":
        return sql_answer(question)
    elif route == "general":
        # For general questions, just use LLM directly without DB context
        from app.llm import get_llm
        try:
            llm = get_llm()
            response = llm.invoke(question)
            answer = response.content.strip() if hasattr(response, "content") else str(response).strip()
        except Exception as e:
            answer = f"Sorry, I couldn't process that. Error: {e}"
        return {"answer": answer, "route": "general", "sources": []}
    else:
        # Default: RAG
        return rag_answer(question)
 