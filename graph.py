# graph.py
"""
graph.py
--------
Builds the LangGraph pipeline:

    scrape → extract → parse ──(ok)──► save → END
         └─(fail)─┘    └─(fail)─┘          └─(fail)──► END
"""

from langgraph.graph import END, StateGraph

from agentstate import WebAgentState
from nodes import node_scrape, node_extract, node_parse, node_save


def _route_after_scrape(state: WebAgentState) -> str:
    return END if state.get("status") == "failed" else "extract"


def _route_after_extract(state: WebAgentState) -> str:
    return END if state.get("status") == "failed" else "parse"


def _route_after_parse(state: WebAgentState) -> str:
    return "save" if state.get("status") != "failed" else END


def build_graph():
    g = StateGraph(WebAgentState)

    g.add_node("scrape",  node_scrape)
    g.add_node("extract", node_extract)
    g.add_node("parse",   node_parse)
    g.add_node("save",    node_save)

    g.set_entry_point("scrape")
    g.add_conditional_edges(
        "scrape",
        _route_after_scrape,
        {"extract": "extract", END: END},
    )
    g.add_conditional_edges(
        "extract",
        _route_after_extract,
        {"parse": "parse", END: END},
    )
    g.add_conditional_edges(
        "parse",
        _route_after_parse,
        {"save": "save", END: END},
    )
    g.add_edge("save", END)

    return g.compile()
