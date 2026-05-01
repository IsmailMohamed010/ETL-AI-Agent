# ── Configure which tables are "entities" ────────────────────────────────────
# Leave empty to auto-detect and ingest all tables
ENTITY_TABLES: list[str] = []
 
 
if __name__ == "__main__":
    force = "--force" in sys.argv
    initialize()
 
    tables_to_ingest = ENTITY_TABLES if ENTITY_TABLES else get_all_tables()
 
    print(f"\nIngesting {len(tables_to_ingest)} entity tables (force={force})...")
 
    for table in tables_to_ingest:
        result = ingest_table(table, force=force)
        status = result.get("status")
        rows   = result.get("rows", "-")
        error  = result.get("error", "")
        print(f"  [{status.upper()}] {table} — rows: {rows} {error}")
 
    print("\n✅ Done.")
 