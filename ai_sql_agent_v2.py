#!/usr/bin/env python3
"""
ai_sql_agent_v2.py (upgrade: typo-correction + smart no-result handling)

Features added:
- fuzzy typo-correction of natural language (columns/keywords)
- when query returns zero rows, the agent inspects filters (e.g. category)
  and queries the DB for close matches, suggests and automatically applies
  corrections and re-runs the query (shows user messages).
- retains LLM fallback + rule-based translator + SQL Server corrections.

Usage examples:
  python ai_sql_agent_v2.py --run "show all products where id between 1500 and 3000 and catigory is b" --csv out.csv
  python ai_sql_agent_v2.py --llm --run "top 10 cheapest products" --csv top10.csv
"""
import os
import re
import argparse
import logging
from typing import Optional, List, Tuple
import difflib

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load .env
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ai_sql_agent_v2")

# Config
SOURCE_DB_URL = os.getenv("SOURCE_DB_URL")
TARGET_DB_URL = os.getenv("TARGET_DB_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # optional
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

DEFAULT_TABLE = "dbo.Products"
DEFAULT_COLUMNS = ["id", "name", "price", "category"]

# Try OpenAI client (v1.0+)
OPENAI_AVAILABLE = False
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False

# -------------------------
# Typos / normalization helpers
# -------------------------
# canonical tokens we accept for fuzzy matching
CANONICAL_WORDS = set([
    "show","list","display","get","products","product","where","and","or",
    "between","in","contains","contain","is","equals","=", "top","first",
    "cheapest","most","expensive","price","id","name","category","cat","sorted",
    "order","by","limit","under","below","less","over","greater","than"
])
# include columns
CANONICAL_WORDS.update(DEFAULT_COLUMNS)

def normalize_nl(nl: str) -> Tuple[str, List[Tuple[str,str]]]:
    """
    Fix common misspellings in NL by fuzzy-matching tokens to a canonical set.
    Returns corrected NL and list of replacements made [(orig, fixed), ...]
    """
    tokens = re.findall(r"\w+|[^\s\w]", nl)  # preserve punctuation as tokens
    corrected = []
    replacements = []
    candidates = list(CANONICAL_WORDS)
    for t in tokens:
        t_low = t.lower()
        # only try to correct alphabetic tokens (skip numbers and punctuation)
        if re.fullmatch(r"[A-Za-z_]+", t_low):
            if t_low in CANONICAL_WORDS:
                corrected.append(t)
            else:
                # try fuzzy match
                match = difflib.get_close_matches(t_low, candidates, n=1, cutoff=0.78)
                if match:
                    corrected_token = match[0]
                    # keep original casing if token in default columns
                    if t.isupper():
                        corrected.append(corrected_token.upper())
                    else:
                        corrected.append(corrected_token)
                    replacements.append((t, corrected_token))
                else:
                    corrected.append(t)
        else:
            corrected.append(t)
    corrected_nl = "".join([
        ("" if re.fullmatch(r"\w+", tok) else tok) if False else (tok if re.fullmatch(r"[^\w\s]", tok) else tok + " ")
        for tok in corrected
    ])
    # above join created spaces too many; better re-create with simple join by space and remove spaces before punctuation
    corrected_nl = " ".join([tok for tok in corrected])
    corrected_nl = re.sub(r"\s+([,.;:!?])", r"\1", corrected_nl)
    return corrected_nl.strip(), replacements

# -------------------------
# Safety & helpers
# -------------------------
def is_select_only(sql: str) -> bool:
    s = sql.strip().lower()
    # allow only SELECT ... ; (basic)
    if not s.startswith("select"):
        return False
    # disallow semantically damaging keywords
    forbidden = ["insert ", "update ", "delete ", "drop ", "alter ", "create ", "truncate ", "exec ", "merge "]
    for kw in forbidden:
        if kw in s:
            return False
    return True

def tox_sql_server_limit_to_top(sql: str) -> str:
    # convert "LIMIT n" at end to "TOP n" after SELECT
    m = re.search(r"limit\s+(\d+)\s*;?$", sql, flags=re.I)
    if m:
        limit_n = m.group(1)
        # remove limit clause
        sql = re.sub(r"\s*limit\s+\d+\s*;?$", ";", sql, flags=re.I).strip()
        sql = re.sub(r"select\s+", f"SELECT TOP {limit_n} ", sql, count=1, flags=re.I)
    return sql

# -------------------------
# Rule-based NL -> T-SQL
# -------------------------
def parse_between(s: str) -> Optional[Tuple[str,str]]:
    m = re.search(r"\bbetween\s+(-?\d+(\.\d+)?)\s+(and|-)\s+(-?\d+(\.\d+)?)\b", s)
    if m:
        return (m.group(1), m.group(4))
    return None

def parse_in_values(s: str) -> Optional[Tuple[str,List[str]]]:
    # pattern: category in A,B or category in ('A','B')
    m = re.search(r"\b(category|name)\s+in\s*\(?\s*([^\)]+)\)?", s)
    if m:
        col = m.group(1)
        vals = [v.strip(" '\"") for v in re.split(r"[,\s]+", m.group(2)) if v.strip()]
        return (col, vals)
    return None

def parse_comparisons(s: str) -> List[str]:
    comps = []
    # price comparisons numeric
    m = re.findall(r"(price)\s*(<=|>=|=|<|>)\s*(-?\d+(\.\d+)?)", s)
    for item in m:
        comps.append(f"{item[0]} {item[1]} {item[2]}")
    # id comparisons
    m2 = re.findall(r"(id)\s*(<=|>=|=|<|>)\s*(\-?\d+)", s)
    for item in m2:
        comps.append(f"{item[0]} {item[1]} {item[2]}")
    return comps

def parse_contains(s: str) -> List[str]:
    clauses = []
    # name contains 'phone' -> name LIKE '%phone%'
    m = re.findall(r"name\s+(?:contains|containing|with|that contains)\s+'?\"?([a-zA-Z0-9_\-\s]+)'?\"?", s)
    for g in m:
        clauses.append(f"name LIKE '%{g.strip()}%'")
    # generic "contains WORD"
    m2 = re.findall(r"contains\s+'?\"?([a-zA-Z0-9_\-\s]+)'?\"?", s)
    for g in m2:
        clauses.append(f"(name LIKE '%{g.strip()}%' OR category LIKE '%{g.strip()}%')")
    return clauses

def parse_top(s: str) -> Optional[int]:
    m = re.search(r"\btop\s+(\d+)\b", s)
    if m:
        return int(m.group(1))
    m2 = re.search(r"\bfirst\s+(\d+)\b", s)
    if m2:
        return int(m2.group(1))
    m3 = re.search(r"\b(\d+)\s+(?:cheapest|most expensive|highest|lowest|top)\b", s)
    if m3:
        return int(m3.group(1))
    return None

def build_where_clauses(nl: str) -> str:
    s = nl.lower()
    clauses = []
    # BETWEEN on id or price
    b = parse_between(s)
    if b:
        # check if mentions id
        if "id" in s:
            clauses.append(f"id BETWEEN {b[0]} AND {b[1]}")
        else:
            clauses.append(f"id BETWEEN {b[0]} AND {b[1]}")
    # IN lists
    pin = parse_in_values(s)
    if pin:
        col, vals = pin
        vals_sql = ", ".join(f"'{v}'" for v in vals)
        clauses.append(f"{col} IN ({vals_sql})")
    # direct equality phrasing: "category is A" or "category = A"
    mcat = re.search(r"(?:category|cat)\s*(?:is|=)\s*'?(?P<v>[A-Za-z0-9_\-]+)'?", s)
    if mcat:
        clauses.append(f"category = '{mcat.group('v')}'")
    # comparisons
    comps = parse_comparisons(s)
    if comps:
        clauses.extend(comps)
    # contains
    conts = parse_contains(s)
    if conts:
        clauses.extend(conts)
    # price wording like "under 50" / "over 100"
    m_under = re.search(r"(?:under|below|less than)\s+(\d+(\.\d+)?)", s)
    if m_under:
        clauses.append(f"price < {m_under.group(1)}")
    m_over = re.search(r"(?:over|greater than|more than)\s+(\d+(\.\d+)?)", s)
    if m_over:
        clauses.append(f"price > {m_over.group(1)}")
    # combined "and" "or" detection is naive: if ' or ' in nl, join with OR
    if " or " in s and clauses:
        return " WHERE " + " OR ".join(clauses)
    if clauses:
        return " WHERE " + " AND ".join(clauses)
    return ""

def parse_order_clause(nl: str) -> str:
    s = nl.lower()
    if "price desc" in s or ("most expensive" in s or "highest" in s):
        if "most expensive" in s or "highest" in s:
            return " ORDER BY price DESC"
    if "cheapest" in s or "lowest" in s:
        return " ORDER BY price ASC"
    if "order by price desc" in s:
        return " ORDER BY price DESC"
    if "order by price" in s or "sorted by price" in s:
        return " ORDER BY price ASC"
    if "order by name" in s or "sorted by name" in s:
        return " ORDER BY name ASC"
    return ""

def nl_to_sql_rule(nl_text: str, default_table: str = DEFAULT_TABLE, default_cols: List[str] = DEFAULT_COLUMNS) -> str:
    s = nl_text.strip()
    sl = s.lower()
    cols_sql = ", ".join(default_cols)
    top_n = parse_top(sl)
    top_clause = f"TOP {top_n} " if top_n else ""
    where_clause = build_where_clauses(sl)
    order_clause = parse_order_clause(sl)
    sql = f"SELECT {top_clause}{cols_sql} FROM {default_table}{where_clause}{order_clause};"
    # ensure SQL Server syntax (no LIMIT)
    sql = tox_sql_server_limit_to_top(sql)
    return sql

# -------------------------
# LLM-based NL -> SQL (OpenAI v1.0+)
# -------------------------
def nl_to_sql_llm(nl_text: str, sample_schema: Optional[str] = None) -> str:
    """
    Uses OpenAI new client (openai>=1.0). If OPENAI_API_KEY not set or client not installed, will raise.
    """
    if not OPENAI_AVAILABLE:
        raise RuntimeError("OpenAI client not installed (openai>=1.0).")
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in environment.")
    client = OpenAI(api_key=OPENAI_API_KEY)
    system = (
        "You are a translator that converts natural language requests into T-SQL for Microsoft SQL Server.\n"
        "Return only a single T-SQL SELECT statement (no explanation). Use TOP for limits, BETWEEN for ranges, "
        "LIKE for contains, and ORDER BY for sorting. Disallow any DML/DDL. Default table is dbo.Products with columns: id, name, price, category.\n"
    )
    prompt = f"{nl_text}\nSQL:"
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
            temperature=0.0,
            max_tokens=300
        )
        # new API returns choices with message.content
        sql = resp.choices[0].message["content"].strip()
    except Exception as e:
        # compatibility fallback: older style
        raise RuntimeError(f"OpenAI error: {e}")
    # normalize to end with ;
    if not sql.endswith(";"):
        sql = sql + ";"
    # convert LIMIT -> TOP if LLM used LIMIT
    sql = tox_sql_server_limit_to_top(sql)
    return sql

# -------------------------
# Execute SQL and ETL + zero-result handling
# -------------------------
def run_sql_fetch(sql: str, src_url: str) -> pd.DataFrame:
    if not is_select_only(sql):
        raise RuntimeError("Only SELECT queries are allowed.")
    # convert LIMIT if present
    sql = tox_sql_server_limit_to_top(sql)
    engine = create_engine(src_url)
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn)
    return df

def write_to_target(df: pd.DataFrame, target_table: str, target_url: str, if_exists: str = "replace"):
    engine = create_engine(target_url)
    df.to_sql(target_table, engine, if_exists=if_exists, index=False)
    logger.info("Wrote table %s", target_table)

def fetch_distinct_values(column: str, src_url: str) -> List[str]:
    """Return distinct values for a column (case-preserved)"""
    engine = create_engine(src_url)
    q = text(f"SELECT DISTINCT {column} FROM {DEFAULT_TABLE} WHERE {column} IS NOT NULL;")
    with engine.connect() as conn:
        rows = conn.execute(q).fetchall()
    return [r[0] for r in rows if r[0] is not None]

def suggest_and_apply_corrections(nl_original: str, where_clause: str, src_url: str) -> Optional[Tuple[str, str]]:
    """
    Inspect WHERE clause for equality filters (category = 'x') and if value not present,
    find close match among existing distinct values. If a close match found, return
    corrected natural-language string and the corrected SQL.
    Returns (corrected_nl, corrected_sql) or None if nothing to do.
    """
    # find category equality
    m = re.search(r"category\s*=\s*'([^']+)'", where_clause, flags=re.I)
    if not m:
        return None
    val = m.group(1)
    # fetch distinct categories from DB
    try:
        distinct = fetch_distinct_values("category", src_url)
    except Exception as e:
        logger.error("Could not fetch distinct category values: %s", e)
        return None
    # case-insensitive compare
    distinct_lower = [str(x).lower() for x in distinct]
    if val.lower() in distinct_lower:
        # exact value exists but maybe case differs; no correction needed
        return None
    # try fuzzy match
    match = difflib.get_close_matches(val.lower(), distinct_lower, n=1, cutoff=0.6)
    if match:
        # map back to original casing value
        idx = distinct_lower.index(match[0])
        corrected_val = distinct[idx]
        # propose corrected NL by replacing the literal in original NL
        corrected_nl = re.sub(r"(category\s*(?:is|=)\s*)'?" + re.escape(val) + r"'?", r"\1'"+str(corrected_val)+"'", nl_original, flags=re.I)
        corrected_sql = nl_to_sql_rule(corrected_nl)
        return corrected_nl, corrected_sql
    return None

# -------------------------
# CLI
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="AI SQL ETL Agent v2 (smart NL->T-SQL; typo correction + zero-result handling)")
    parser.add_argument("--llm", action="store_true", help="Use OpenAI LLM (requires OPENAI_API_KEY)")
    parser.add_argument("--run", type=str, help="Natural-language query or raw SQL to run")
    parser.add_argument("--csv", type=str, help="Export results to CSV")
    parser.add_argument("--target-table", type=str, help="Write results to this table in TARGET_DB_URL")
    parser.add_argument("--show-sql", action="store_true", help="Print generated SQL and exit (no DB call)")
    args = parser.parse_args()

    if not args.run:
        parser.print_help()
        return

    nl_original = args.run.strip()
    # 1) normalize/correct common typos before parsing
    nl_corrected, replacements = normalize_nl(nl_original)
    if replacements:
        print("Note: corrected possible typos:", ", ".join(f"'{a}' -> '{b}'" for a, b in replacements))

        logger.info("Normalized NL: %s", nl_corrected)
    else:
        nl_corrected = nl_original

    # Decide SQL generation method
    if args.llm and OPENAI_AVAILABLE and OPENAI_API_KEY:
        try:
            sql = nl_to_sql_llm(nl_corrected)
            logger.info("SQL (LLM): %s", sql)
        except Exception as e:
            logger.error("LLM failed: %s — falling back to rule-based", e)
            sql = nl_to_sql_rule(nl_corrected)
    else:
        sql = nl_to_sql_rule(nl_corrected)

    # If user provided raw SQL starting with SELECT, respect it
    if nl_original.strip().lower().startswith("select"):
        sql = nl_original if nl_original.strip().endswith(";") else nl_original.strip() + ";"

    if args.show_sql:
        print(sql)
        return

    print("SQL:", sql)
    if not SOURCE_DB_URL:
        raise RuntimeError("SOURCE_DB_URL not set in environment (.env)")
    # run query
    df = run_sql_fetch(sql, SOURCE_DB_URL)
    print("Rows returned:", len(df))
    # if zero rows, try to diagnose and auto-correct (only for category equality currently)
    if df.empty:
        # attempt to get where clause (simple parse)
        where_m = re.search(r"where\s+(.+?);?$", sql, flags=re.I)
        where_clause = where_m.group(1) if where_m else ""
        suggestion = suggest_and_apply_corrections(nl_corrected, where_clause, SOURCE_DB_URL)
        if suggestion:
            corrected_nl, corrected_sql = suggestion
            print(f"No rows returned. I found a likely typo in your filter and applied correction: {corrected_nl}")
            print("Re-running corrected SQL:", corrected_sql)
            df2 = run_sql_fetch(corrected_sql, SOURCE_DB_URL)
            print("Rows returned after correction:", len(df2))
            df = df2  # use corrected results going forward
        else:
            # suggest possible values to user
            mcat = re.search(r"category\s*=\s*'([^']+)'", where_clause, flags=re.I)
            if mcat:
                val = mcat.group(1)
                try:
                    distinct = fetch_distinct_values("category", SOURCE_DB_URL)
                    # show top 10 distinct examples
                    sample = distinct[:10]
                    print(f"No rows returned for category = '{val}'. Available sample categories: {sample}")
                except Exception:
                    print(f"No rows returned for category = '{val}'. Could not fetch available values.")
            else:
                print("No rows returned. Please check your query or try a broader filter.")
    # export CSV
    if args.csv:
        try:
            df.to_csv(args.csv, index=False)
            print(f"Exported to {args.csv}")
        except Exception as e:
            print(f"Could not export to CSV: {e}")
    # write to target DB if requested
    if args.target_table:
        if not TARGET_DB_URL:
            raise RuntimeError("TARGET_DB_URL not set in environment (.env)")
        write_to_target(df, args.target_table, TARGET_DB_URL)
        print(f"Wrote table {args.target_table}")
    print("Done.")

if __name__ == "__main__":
    main()
