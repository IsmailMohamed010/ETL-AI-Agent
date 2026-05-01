"""
app/vector_store.py
FAISS vector store — save, load, add documents, search.
Persists to disk so you don't re-ingest on every restart.
"""
 
import logging
import os
from typing import List
 
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
 
from app.config import VECTOR_STORE_PATH
from app.embeddings import get_embeddings
 
logger = logging.getLogger(__name__)
 
_store: FAISS | None = None
 
 
# ── Load / Save ───────────────────────────────────────────────────────────────
 
def load_store() -> None:
    """Loads the FAISS index from disk if it exists."""
    global _store
    index_file = os.path.join(VECTOR_STORE_PATH, "index.faiss")
    if os.path.exists(index_file):
        logger.info(f"Loading vector store from '{VECTOR_STORE_PATH}'...")
        _store = FAISS.load_local(
            VECTOR_STORE_PATH,
            get_embeddings(),
            allow_dangerous_deserialization=True,
        )
        logger.info("Vector store loaded.")
    else:
        logger.info("No existing vector store found — will create on first ingest.")
 
 
def save_store() -> None:
    """Persists the current FAISS index to disk."""
    if _store is not None:
        os.makedirs(VECTOR_STORE_PATH, exist_ok=True)
        _store.save_local(VECTOR_STORE_PATH)
        logger.info(f"Vector store saved to '{VECTOR_STORE_PATH}'.")
 
 
# ── Documents ─────────────────────────────────────────────────────────────────
 
def add_documents(docs: List[Document]) -> None:
    """
    Adds documents to the vector store and persists to disk.
    Creates a new store if one doesn't exist yet.
    """
    global _store
    if not docs:
        logger.warning("add_documents called with empty list — skipping.")
        return
 
    if _store is None:
        logger.info("Creating new FAISS vector store...")
        _store = FAISS.from_documents(docs, get_embeddings())
    else:
        _store.add_documents(docs)
 
    save_store()
    logger.info(f"Added {len(docs)} document chunks to vector store.")
 
 
def similarity_search(query: str, k: int = 5) -> List[Document]:
    """
    Returns the top-k most relevant documents for the query.
    """
    if _store is None:
        logger.warning("Vector store is empty — no results.")
        return []
    return _store.similarity_search(query, k=k)
 
 
def source_exists(source_name: str) -> bool:
    """
    Checks whether a source has already been ingested.
    Avoids duplicate ingestion on re-runs.
    """
    if _store is None:
        return False
    try:
        docs = _store.similarity_search(source_name, k=1)
        return any(d.metadata.get("source") == source_name for d in docs)
    except Exception:
        return False
 
 
def get_store() -> FAISS | None:
    """Returns the raw FAISS store (used by retriever)."""
    return _store
 