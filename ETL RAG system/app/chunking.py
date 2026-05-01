"""
app/chunking.py
Converts raw text into LangChain Document chunks for ingestion.
"""
 
import logging
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
 
from app.config import CHUNK_SIZE, CHUNK_OVERLAP
 
logger = logging.getLogger(__name__)
 
 
def _get_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
 
 
def text_to_documents(
    text: str,
    source_name: str,
    metadata: dict | None = None,
) -> list[Document]:
    """
    Splits `text` into chunks and wraps each chunk in a LangChain Document.
    """
    if not text or not text.strip():
        logger.warning(f"Empty text for source '{source_name}', skipping.")
        return []
 
    base_meta = {"source": source_name}
    if metadata:
        base_meta.update(metadata)
 
    splitter = _get_splitter()
    chunks = splitter.split_text(text)
 
    docs = [
        Document(page_content=chunk, metadata={**base_meta, "chunk_index": i})
        for i, chunk in enumerate(chunks)
    ]
    logger.info(f"'{source_name}' → {len(docs)} chunks from {len(text)} chars.")
    return docs
 
 
def dataframe_to_documents(
    df,
    source_name: str,
    metadata: dict | None = None,
) -> list[Document]:
    """
    Converts a pandas DataFrame into chunked Documents.
    Each row becomes a key:value text block, then all rows are joined and split.
    """
    if df is None or df.empty:
        logger.warning(f"Empty DataFrame for source '{source_name}', skipping.")
        return []
 
    rows_text = []
    for _, row in df.iterrows():
        row_str = "\n".join(f"{col}: {val}" for col, val in row.items())
        rows_text.append(row_str)
 
    full_text = "\n\n---\n\n".join(rows_text)
    return text_to_documents(full_text, source_name, metadata)
 




