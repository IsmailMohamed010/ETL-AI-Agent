from langgraph.graph import StateGraph, END
from agentstate import WebAgentState
from nodes import node_extract, node_validate, node_save

def build_graph():
    g = StateGraph(WebAgentState)

    g.add_node("extract", node_extract)
    g.add_node("validate", node_validate)
    g.add_node("save", node_save)

    g.set_entry_point("extract")
    g.add_edge("extract", "validate")

    # If validation fails, stop; else save
    def route_after_validate(state: WebAgentState):
        if state.get("status") == "failed":
            return END
        return "save"

    g.add_conditional_edges("validate", route_after_validate, {"save": "save", END: END})
    g.add_edge("save", END)

    return g.compile()
