#!/usr/bin/env python
import os
import re
import argparse
from typing import Dict, Any, List

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
# NORMALIZATION & TYPO FIXING
# ======================================================
TYPO_FIXES = {
    "catigory": "category",
    "pricerang": "pricerange",
    "pricerangee": "pricerange",
    "price range": "pricerange",
    "betwen": "between",
}

STOPWORDS = {
    "show", "all", "records", "products", "rows",
    "where", "that", "with", "which", "is"
}

# ======================================================
# SCHEMA HELPERS
# ======================================================
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

# ======================================================
# NL → SQL
# ======================================================
def normalize_nl(text: str) -> str:
    text = text.lower()
    for k, v in TYPO_FIXES.items():
        text = text.replace(k, v)
    return text

def nl_to_sql(state: Dict[str, Any]) -> Dict[str, Any]:
    nl = normalize_nl(state["nl"])
    table = state["source_table"]

    engine = create_engine(SOURCE_DB_URL)
    real_columns = get_table_columns(engine, table)

    filters = []

    # id BETWEEN X AND Y
    m = re.search(r"id\s+(?:is\s+)?between\s+(\d+)\s+and\s+(\d+)", nl)
    if m:
        filters.append(f"id BETWEEN {m.group(1)} AND {m.group(2)}")

    # column = value
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

    if "where" in nl and not filters:
        raise RuntimeError("❌ Cannot understand filters in your request")

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
        print(f"CSV saved → {state['csv']}")

    if state.get("target_table"):
        engine = create_engine(TARGET_DB_URL)
        df.to_sql(state["target_table"], engine, if_exists="replace", index=False)
        print(f"Loaded table → {state['target_table']}")

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
# CLI
# ======================================================
def main():
    parser = argparse.ArgumentParser("Generic LangGraph Regex SQL ETL Agent")
    parser.add_argument("--run", required=True)
    parser.add_argument("--source-table", required=True)
    parser.add_argument("--target-table")
    parser.add_argument("--csv")
    args = parser.parse_args()

    app = build_graph()

    state = {
        "nl": args.run,
        "source_table": args.source_table,
        "target_table": args.target_table,
        "csv": args.csv
    }

    result = app.invoke(state)

    print("\nGenerated SQL:")
    print(result["sql"])
    print(f"Rows returned: {len(result['df'])}")

if __name__ == "__main__":
    main()
