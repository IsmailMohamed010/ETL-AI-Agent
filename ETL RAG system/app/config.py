"""
app/config.py
Loads all configuration from environment variables / .env file.
"""
 
import os
from dotenv import load_dotenv
 
load_dotenv()
 
# ── SQL Server ────────────────────────────────────────────────────────────────
DB_SERVER   = os.getenv("DB_SERVER", "localhost")
DB_NAME     = os.getenv("DB_NAME", "etl_db")
DB_USER     = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_DRIVER   = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
 
# ── Embeddings (HuggingFace, local, free) ─────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
 
# ── LLM (Ollama, local, free) ─────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3")
 
# ── Vector Store (FAISS, local) ───────────────────────────────────────────────
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", "data/vector_store")
 
# ── RAG settings ──────────────────────────────────────────────────────────────
TOP_K_RETRIEVAL  = int(os.getenv("TOP_K_RETRIEVAL", "5"))
MAX_ROWS_INGEST  = int(os.getenv("MAX_ROWS_INGEST", "500"))   # max rows per table to ingest
CHUNK_SIZE       = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP    = int(os.getenv("CHUNK_OVERLAP", "50"))
 
# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")