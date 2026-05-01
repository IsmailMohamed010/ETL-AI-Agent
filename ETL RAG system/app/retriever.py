"""
app/retriever.py
Retrieves relevant documents from the vector store for a given query.
"""
 
import logging
from langchain_core.documents import Document
from app.vector_store import similarity_search
from app.config import TOP_K_RETRIEVAL
 
logger = logging.getLogger(__name__)
 
 
def retrieve(query: str, k: int = TOP_K_RETRIEVAL) -> list[Document]:
    """
    Returns the top-k most relevant documents from the vector store.
 
    Args:
        query: The user's question.
        k:     Number of documents to retrieve.
 
    Returns:
        List of LangChain Document objects.
    """
    logger.info(f"Retrieving top-{k} docs for query: '{query[:80]}'")
    docs = similarity_search(query, k=k)
    logger.info(f"Retrieved {len(docs)} documents.")
    return docs
 
 
def format_context(docs: list[Document]) -> str:
    """
    Formats retrieved documents into a single context string for the LLM prompt.
    Includes source metadata so the LLM knows where each chunk came from.
    """
    if not docs:
        return "No relevant information found in the database."
 
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        parts.append(f"[Source {i}: {source}]\n{doc.page_content}")
 
    return "\n\n---\n\n".join(parts)
 
 
def retrieve_and_format(query: str, k: int = TOP_K_RETRIEVAL) -> tuple[str, list[str]]:
    """
    Retrieves documents and returns (formatted_context, list_of_sources).
    """
    docs = retrieve(query, k=k)
    context = format_context(docs)
    sources = list({doc.metadata.get("source", "unknown") for doc in docs})
    return context, sources
 