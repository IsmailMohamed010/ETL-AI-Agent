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

    parser.add_argument("--run", required=True)
    parser.add_argument("--source-tables", required=True)
    parser.add_argument("--output-folder", required=True)
    parser.add_argument("--target-table")

    args = parser.parse_args()

    tables = [t.strip() for t in args.source_tables.split(",") if t.strip()]

    if not tables:
        raise ValueError("❌ No valid tables provided")

    if not os.path.exists(args.output_folder):
        os.makedirs(args.output_folder)
        print(f"📁 Created folder: {args.output_folder}")

    app = build_graph()

    success, failed = 0, 0

    for table in tables:

        print(f"\n🔄 [{datetime.now().strftime('%H:%M:%S')}] Processing: {table}")

        # 🔥 AUTO NAME OUTPUT FILE
        output_name = get_next_output_name(args.output_folder)
        output_csv = os.path.join(args.output_folder, output_name)

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
    print(f"❌ Failed: {failed}")
    print("==============================")

# ======================================================
# ENTRY POINT
# ======================================================
if __name__ == "__main__":
    main()