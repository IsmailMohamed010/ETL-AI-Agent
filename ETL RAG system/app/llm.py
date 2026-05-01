"""
app/llm.py
Ollama LLM singleton — returns a cached LangChain ChatOllama instance.
"""
 
import logging
from langchain_ollama import ChatOllama
from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL
 
logger = logging.getLogger(__name__)
 
_llm = None
 
 
def get_llm() -> ChatOllama:
    """
    Returns a singleton ChatOllama instance.
    Reuses the same instance across all calls to avoid re-initialization overhead.
    """
    global _llm
    if _llm is None:
        logger.info(f"Loading LLM: {OLLAMA_MODEL} from {OLLAMA_BASE_URL}")
        _llm = ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0,          # deterministic answers for data queries
            timeout=120,            # seconds — give Ollama time to respond
        )
        logger.info("LLM loaded.")
    return _llm
 