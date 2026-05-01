"""
app/embeddings.py
Local, free embeddings using HuggingFace sentence-transformers.
No API key required.
"""
 
import logging
from langchain_huggingface import HuggingFaceEmbeddings
from app.config import EMBEDDING_MODEL
 
logger = logging.getLogger(__name__)
 
_embeddings_instance = None
 
 
def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Returns a singleton HuggingFaceEmbeddings instance.
    Downloads the model on first call (cached locally after that).
    """
    global _embeddings_instance
    if _embeddings_instance is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embeddings_instance = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("Embedding model loaded.")
    return _embeddings_instance