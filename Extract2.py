#!/usr/bin/env python
import os
import re
import argparse
from typing import Dict, Any, List
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# ======================================================
# ENV
# ======================================================
load_dotenv()

SOURCE_DB_URL = os.getenv("SOURCE_DB_URL")
TARGET_DB_URL = os.getenv("TARGET_DB_URL")

if not SOURCE_DB_URL or not TARGET_DB_URL:
    raise RuntimeError("❌ SOURCE_DB_URL and TARGET_DB_URL must be set")

# ======================================================
# ⚙️  FIXED CONFIGURATION
# ======================================================
OUTPUT_FOLDER = r"F:\last_part1\Grad_project\out_extract"

# ─────────────────────────────────────────────────────
# 📋 LIST ALL YOUR DATABASE TABLES HERE (lowercase).
#    The agent will auto-detect any of these mentioned
#    in your natural-language command.
# ─────────────────────────────────────────────────────
KNOWN_TABLES = {
    "products",
    "orders",
    "customers",
    "users",
    "sales",
    "inventory",
    "payments",
    "employees",
    "categories",
    "suppliers",
    # ← add more tables here as needed
}

# ======================================================
# AUTO OUTPUT NAMING 🔥
# ======================================================
def get_next_output_name(folder_path, prefix="output"):

    existing_files = os.listdir(folder_path)

    numbers = []

    for f in existing_files:
        match = re.match(rf"{prefix}(\d+)\.csv", f)
        if match:
            numbers.append(int(match.group(1)))

    next_number = max(numbers) + 1 if numbers else 1

    return f"{prefix}{next_number}.csv"


# ======================================================
# 🧠 SMART TABLE EXTRACTOR
#    Reads the NL command and returns all table names.
#
#    Strategies (applied in order, results merged):
#    1. Explicit keywords  → "from X", "in X", "table X", "extract X"
#    2. KNOWN_TABLES scan  → any word that matches your known table list
#    3. Quoted names       → words inside backticks or single quotes
# ======================================================
def extract_tables_from_nl(nl: str) -> List[str]:

    nl_lower = nl.lower()
    found = set()

    # ── Strategy 1: explicit relational / action keywords ──
    # Patterns: "from X", "in X", "table X", "extract X",
    #           "join X", "into X", "on X"
    keyword_pattern = re.compile(
        r"(?:from|in|table|extract|join|into|on)\s+([a-z_][a-z0-9_]*)",
        re.IGNORECASE
    )
    for match in keyword_pattern.finditer(nl_lower):
        candidate = match.group(1).strip()
        if candidate not in {"the", "a", "an", "all", "each", "every"}:
            found.add(candidate)

    # ── Strategy 2: scan for any KNOWN_TABLES word ──
    words = re.findall(r"[a-z_][a-z0-9_]*", nl_lower)
    for word in words:
        if word in KNOWN_TABLES:
            found.add(word)

    # ── Strategy 3: quoted / backtick names ──
    quoted_pattern = re.compile(r"[`'\"]([a-z_][a-z0-9_]*)[`'\"]", re.IGNORECASE)
    for match in quoted_pattern.finditer(nl_lower):
        found.add(match.group(1).lower())

    # ── Validate against KNOWN_TABLES (warn on unknowns) ──
    validated, unknown = [], []
    for t in sorted(found):
        if t in KNOWN_TABLES:
            validated.append(t)
        else:
            unknown.append(t)

    if unknown:
        print(f"⚠️  Detected table-like names not in KNOWN_TABLES (will attempt anyway): {unknown}")
        validated.extend(unknown)   # still try them — DB will reject if truly wrong

    if not validated:
        raise ValueError(
            "❌ Could not detect any table names from your command.\n"
            "   Tips:\n"
            "   • Use 'from <table>'  →  'show id between 1 and 100 from products'\n"
            "   • Use 'extract <table>' →  'extract orders where status is active'\n"
            "   • Add your table name to KNOWN_TABLES at the top of the script."
        )

    return validated


# ======================================================
# NL → SQL HELPERS
# ======================================================
TYPO_FIXES = {}

STOPWORDS = {
    "show", "all", "records", "products", "rows",
    "where", "that", "with", "which", "is"
}

def get_table_columns(engine, table: str) -> List[str]:
    sql = """
    SELECT COLUMN_NAME
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = :table
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"table": table}).fetchall()
    return [r[0].lower() for r in rows]

def match_column(user_col: str, real_columns: List[str]) -> str | None:
    user_col = user_col.lower()

    if user_col in real_columns:
        return user_col

    for col in real_columns:
        if user_col in col or col in user_col:
            return col

    return None

def normalize_nl(text: str) -> str:
    text = text.lower()
    for k, v in TYPO_FIXES.items():
        text = text.replace(k, v)
    return text


# ======================================================
# NL → SQL
# ======================================================
def nl_to_sql(state: Dict[str, Any]) -> Dict[str, Any]:
    nl = normalize_nl(state["nl"])
    table = state["source_table"]

    engine = create_engine(SOURCE_DB_URL)
    real_columns = get_table_columns(engine, table)

    filters = []

    m = re.search(r"id\s+(?:is\s+)?between\s+(\d+)\s+and\s+(\d+)", nl)
    if m:
        filters.append(f"id BETWEEN {m.group(1)} AND {m.group(2)}")

    pairs = re.findall(r"(\w+)\s+(?:is|=)\s+([a-z0-9_]+)", nl)
    for col, val in pairs:
        if col in STOPWORDS or col == "id":
            continue

        matched = match_column(col, real_columns)
        if not matched:
            raise RuntimeError(
                f"❌ Column '{col}' does not exist in table '{table}'. "
                f"Available columns: {', '.join(real_columns)}"
            )

        filters.append(f"{matched} = '{val.upper()}'")

    where_sql = ""
    if filters:
        where_sql = " WHERE " + " AND ".join(filters)

    sql = f"SELECT * FROM {table}{where_sql};"

    state["sql"] = sql
    return state


# ======================================================
# EXECUTION
# ======================================================
def run_query(state: Dict[str, Any]) -> Dict[str, Any]:
    engine = create_engine(SOURCE_DB_URL)
    with engine.connect() as conn:
        df = pd.read_sql(text(state["sql"]), conn)

    state["df"] = df
    return state

def write_outputs(state: Dict[str, Any]) -> Dict[str, Any]:
    df = state["df"]

    if state.get("csv"):
        df.to_csv(state["csv"], index=False)
        print(f"💾 CSV saved → {state['csv']}")

    if state.get("target_table"):
        engine = create_engine(TARGET_DB_URL)
        df.to_sql(state["target_table"], engine, if_exists="replace", index=False)
        print(f"🗄️ Loaded table → {state['target_table']}")

    return state


# ======================================================
# LANGGRAPH
# ======================================================
def build_graph():
    g = StateGraph(dict)

    g.add_node("nl_to_sql", nl_to_sql)
    g.add_node("run_query", run_query)
    g.add_node("write_outputs", write_outputs)

    g.set_entry_point("nl_to_sql")
    g.add_edge("nl_to_sql", "run_query")
    g.add_edge("run_query", "write_outputs")
    g.add_edge("write_outputs", END)

    return g.compile()


# ======================================================
# MAIN
# ======================================================
def main():

    parser = argparse.ArgumentParser("SQL Extraction Agent")

    parser.add_argument(
        "--run",
        required=True,
        help=(
            "Natural-language extraction command. "
            "Table names are detected automatically. Examples:\n"
            "  'show id between 1 and 500 from products'\n"
            "  'extract orders and customers where status is active'\n"
            "  'show all records from users'"
        )
    )
    parser.add_argument("--target-table", help="Optional: load result into this target DB table")

    args = parser.parse_args()

    # ── Ensure output folder exists ──
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"📁 Created output folder: {OUTPUT_FOLDER}")

    # ── Smart table detection ──
    print(f"\n🧠 Detecting tables from command: \"{args.run}\"")
    tables = extract_tables_from_nl(args.run)
    print(f"📋 Tables to extract: {tables}")

    app = build_graph()

    success, failed = 0, 0

    for table in tables:

        print(f"\n🔄 [{datetime.now().strftime('%H:%M:%S')}] Processing: {table}")

        # 🔥 AUTO NAME OUTPUT FILE
        output_name = get_next_output_name(OUTPUT_FOLDER)
        output_csv  = os.path.join(OUTPUT_FOLDER, output_name)

        print(f"🆕 Generated file name: {output_name}")

        state = {
            "nl": args.run,
            "source_table": table,
            "target_table": args.target_table,
            "csv": output_csv
        }

        try:
            result = app.invoke(state)

            df = result.get("df")

            if df is None:
                raise RuntimeError("No dataframe returned")

            print(f"🧾 SQL: {result.get('sql')}")

            if df.empty:
                print("⚠️ No data returned")
            else:
                print(f"✅ Rows extracted: {len(df)}")

            success += 1

        except Exception as e:
            print(f"❌ Failed for {table}: {e}")
            failed += 1

    print("\n==============================")
    print("📊 EXTRACTION SUMMARY")
    print(f"✅ Success: {success}")
    print(f"❌ Failed:  {failed}")
    print("==============================")


# ======================================================
# ENTRY POINT
# ======================================================
if __name__ == "__main__":
    main()