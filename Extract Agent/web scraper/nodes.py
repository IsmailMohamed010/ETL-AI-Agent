# nodes.py
"""
nodes.py
--------
LangGraph node functions for the 4-step extraction pipeline:
  1. scrape   → raw page text
  2. extract  → JSON via LLM
  3. parse    → flat list[dict] rows
  4. save     → CSV + SQLite

Fixes applied (v3)
──────────────────
1. extractor now always returns a list — updated node_extract to store
   it correctly in extracted_json and handle the empty-list failure case.
2. node_parse updated: since extractor now returns a flat list of dicts,
   _flatten_to_rows is largely bypassed — rows come in already flat.
   Dedup is still applied as a safety net.
3. agentstate.py extracted_json type widened to dict | list (comment only —
   TypedDict stays flexible with total=False).
"""

import logging
from typing import Any

from agentstate import WebAgentState
from web_logic import scrape_page, save_to_csv, save_to_db
from extractor_llm import extract_from_text
from prompt_generator import generate_extraction_prompt

logger = logging.getLogger(__name__)


# ── Step 1: Scrape ─────────────────────────────────────────────────────────────

def node_scrape(state: WebAgentState) -> dict[str, Any]:
    """Fetch the webpage and return clean plain text."""
    try:
        cfg = state.get("config", {})
        url = state["url"]

        content = scrape_page(
            url             = url,
            wait_selector   = cfg.get("wait_selector"),
            infinite_scroll = cfg.get("infinite_scroll", False),
        )

        return {"raw_content": content, "status": "running"}

    except Exception as exc:
        logger.error("node_scrape failed: %s", exc)
        return {
            "errors": state.get("errors", []) + [f"scrape: {exc}"],
            "status": "failed",
        }


# ── Step 2: Extract ────────────────────────────────────────────────────────────

def node_extract(state: WebAgentState) -> dict[str, Any]:
    """Send raw text + search query to the LLM and get back a list of dicts."""
    try:
        raw_content  = state.get("raw_content", "")
        search_query = state.get("search_query", "all important information")

        if not raw_content:
            raise ValueError("raw_content is empty — scraping may have failed.")

        logger.info("Raw content length: %d chars", len(raw_content))

        refined_prompt = generate_extraction_prompt(search_query)
        logger.info("Ollama refined prompt (first 200): %s", refined_prompt[:200])

        result = extract_from_text(raw_content, refined_prompt)
        logger.info("Extraction complete. Items: %d", len(result) if isinstance(result, list) else 1)

        # Detect complete extraction failure (empty list)
        if isinstance(result, list) and len(result) == 0:
            msg = "LLM extraction returned 0 items — check scrape output and query."
            logger.error(msg)
            return {
                "errors": state.get("errors", []) + [f"extract: {msg}"],
                "status": "failed",
            }

        # Detect legacy _parse_error dict (shouldn't happen with new extractor, but guard anyway)
        if isinstance(result, dict) and result.get("_parse_error"):
            raw_snippet = str(result.get("raw_output", ""))[:300]
            msg = f"LLM output could not be parsed as JSON. Raw snippet: {raw_snippet!r}"
            logger.error(msg)
            return {
                "errors": state.get("errors", []) + [f"extract: {msg}"],
                "status": "failed",
            }

        return {"extracted_json": result, "status": "running"}

    except Exception as exc:
        logger.error("node_extract failed: %s", exc, exc_info=True)
        return {
            "errors": state.get("errors", []) + [f"extract: {exc}"],
            "status": "failed",
        }


# ── Step 3: Parse ──────────────────────────────────────────────────────────────

def node_parse(state: WebAgentState) -> dict[str, Any]:
    """
    Normalize extracted_json into a flat list[dict] ready for CSV/DB.
    The new extractor already returns a flat list, so this is mostly pass-through
    with dedup and source_url injection.
    """
    try:
        data = state.get("extracted_json", {})
        url  = state.get("url", "")

        rows = _flatten_to_rows(data, source_url=url)
        rows = _deduplicate(rows)

        if not rows:
            msg = "Parse step produced 0 rows."
            logger.warning(msg)
            return {
                "errors": state.get("errors", []) + [msg],
                "status": "failed",
            }

        logger.info("Parsed %d unique rows.", len(rows))
        return {"parsed_rows": rows, "status": "running"}

    except Exception as exc:
        logger.error("node_parse failed: %s", exc, exc_info=True)
        return {
            "errors": state.get("errors", []) + [f"parse: {exc}"],
            "status": "failed",
        }


def _deduplicate(rows: list[dict]) -> list[dict]:
    """Remove duplicate rows (compare all keys except _source_url)."""
    seen  = set()
    clean = []
    for row in rows:
        key = tuple(
            (k, str(v)) for k, v in sorted(row.items()) if k != "_source_url"
        )
        if key not in seen:
            seen.add(key)
            clean.append(row)
    return clean


def _flatten_to_rows(data, source_url: str) -> list[dict]:
    """
    Convert any JSON structure to a list of flat dicts.
    The extractor now returns a list, so the first branch handles the normal case.
    """
    if isinstance(data, list):
        rows = []
        for item in data:
            if isinstance(item, dict):
                flat = _dot_flatten(item, source_url)
                rows.append(flat)
            else:
                rows.append({"value": str(item), "_source_url": source_url})
        return rows

    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, list) and all(isinstance(i, dict) for i in val):
                return [
                    _dot_flatten({**item, "_source_url": source_url}, source_url)
                    for item in val
                ]
        return [_dot_flatten(data, source_url)]

    return [{"value": str(data), "_source_url": source_url}]


def _dot_flatten(d: dict, source_url: str, prefix: str = "") -> dict:
    """Recursively flatten nested dict using dot notation keys."""
    flat = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(_dot_flatten(v, source_url="", prefix=key))
        elif isinstance(v, list):
            flat[key] = ", ".join(str(i) for i in v)
        else:
            flat[key] = v
    if not prefix:
        flat["_source_url"] = source_url
    return flat


# ── Step 4: Save ───────────────────────────────────────────────────────────────

def node_save(state: WebAgentState) -> dict[str, Any]:
    """Write parsed_rows to CSV and/or SQLite."""
    try:
        cfg  = state.get("config", {})
        rows = state.get("parsed_rows", [])

        if not rows:
            raise ValueError("No parsed rows to save.")

        if cfg.get("save_csv", True):
            save_to_csv(rows)

        if cfg.get("save_db", True):
            save_to_db(rows)

        return {"status": "done"}

    except Exception as exc:
        logger.error("node_save failed: %s", exc)
        return {
            "errors": state.get("errors", []) + [f"save: {exc}"],
            "status": "failed",
        }
