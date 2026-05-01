from app.agent import initialize
from app.db import get_all_tables
from app.summarizer import summarize_table
from app.vector_store import add_documents
from app.Chunking import text_to_documents
 
if __name__ == "__main__":
    initialize()
    tables = get_all_tables()
    print(f"\nGenerating summaries for {len(tables)} tables...\n")
 
    for table in tables:
        print(f"  Summarizing '{table}'...")
        summary = summarize_table(table)
        docs = text_to_documents(
            summary,
            source_name=f"{table}__summary",
            metadata={"type": "summary", "table": table},
        )
        add_documents(docs)
        print(f"  ✅ Summary added for '{table}'.")
 
    print("\n✅ All summaries ingested.")
 