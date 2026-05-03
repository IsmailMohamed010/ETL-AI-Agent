# agentstate.py
"""
agentstate.py
-------------
Shared state schema for the Web Extraction Agent.
"""

from typing import Optional
from typing_extensions import TypedDict


class AgentConfig(TypedDict):
    save_csv:        bool
    save_db:         bool
    wait_selector:   Optional[str]
    infinite_scroll: bool


class WebAgentState(TypedDict, total=False):
    # ── User inputs ───────────────────────────────────────────
    url:          str            # Single website URL to scrape
    search_query: str            # What to look for / extract (e.g. "product prices and names")

    # ── Config ────────────────────────────────────────────────
    config: AgentConfig

    # ── Pipeline outputs ──────────────────────────────────────
    raw_content:    str          # Raw text scraped from the page
    extracted_json: list[dict]   # LLM-parsed JSON
    parsed_rows:    list[dict]   # Flattened rows ready for CSV/DB
    errors:         list[str]
    status:         str          # "init" | "running" | "failed" | "done"
