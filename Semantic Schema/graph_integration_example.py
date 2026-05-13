"""
graph_integration_example.py
-----------------------------
Shows how to integrate the Semantic Schema node into the existing pipeline.

BEFORE:  scrape → extract → parse → save
AFTER:   scrape → extract → parse → semantic_schema → save

The "save" node should read from `normalized_rows` instead of `parsed_rows`
when the semantic schema step is enabled.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../Extract Agent/web scraper"))

from langgraph.graph import StateGraph, END

# Existing nodes (from the web scraper pipeline)
from nodes import node_scrape, node_extract, node_parse, node_save

# New semantic schema node
from schema_node import node_semantic_schema


def _node_save_normalized(state):
    """
    Wrapper: swap parsed_rows ← normalized_rows before calling node_save.
    This lets the existing save node work unchanged.
    """
    if state.get("normalized_rows"):
        state = {**state, "parsed_rows": state["normalized_rows"]}
    return node_save(state)


def build_graph_with_schema():
    g = StateGraph(dict)

    g.add_node("scrape",          node_scrape)
    g.add_node("extract",         node_extract)
    g.add_node("parse",           node_parse)
    g.add_node("semantic_schema", node_semantic_schema)   # ← NEW
    g.add_node("save",            _node_save_normalized)

    g.set_entry_point("scrape")

    def _continue_or_fail(state):
        return "failed" if state.get("status") == "failed" else "ok"

    for src, dst in [
        ("scrape",          "extract"),
        ("extract",         "parse"),
        ("parse",           "semantic_schema"),
        ("semantic_schema", "save"),
    ]:
        g.add_conditional_edges(
            src,
            _continue_or_fail,
            {"ok": dst, "failed": END},
        )

    g.add_edge("save", END)
    return g.compile()


# ── Example usage ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    app = build_graph_with_schema()

    initial_state = {
        "url":          "https://fbref.com/en/comps/9/Premier-League-Stats",
        "search_query": "player stats goals assists",
        "config": {
            "save_csv":             True,
            "save_db":              True,
            "schema_drop_unknown":  False,
            "schema_add_meta":      True,
        },
        "raw_content":    "",
        "extracted_json": [],
        "parsed_rows":    [],
        "errors":         [],
        "status":         "init",
    }

    final = app.invoke(initial_state)

    print("\n── Semantic Schema ──────────────────────────────────────")
    print(json.dumps(final.get("semantic_schema", {}), indent=2, ensure_ascii=False))

    print("\n── Validation ───────────────────────────────────────────")
    print(json.dumps(final.get("schema_validation", {}), indent=2))

    print("\n── Normalized rows (first 3) ────────────────────────────")
    for row in (final.get("normalized_rows") or [])[:3]:
        print(json.dumps(row, ensure_ascii=False))
