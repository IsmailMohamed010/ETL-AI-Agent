from graph import build_graph
from agentstate import WebAgentState

if __name__ == "__main__":

    app = build_graph()

    initial_state: WebAgentState = {
        "urls": [
            {
                "url": "https://books.toscrape.com/catalogue/page-{}.html",
                "doc_type": "html"
            }
        ],
        "config": {
            "pagination": {
                "enabled": True,
                "start": 1,
                "end": 3
            },
            "wait_selector": None,
            "infinite_scroll": False,
            "save_csv": True,
            "save_db": True
        },
        "extracted_data": [],
        "errors": [],
        "status": "init"
    }

    final_state = app.invoke(initial_state)

    print("\n=== AGENT FINISHED ===")
    print("Status:", final_state.get("status"))
    print("Pages scraped:", len(final_state.get("extracted_data", [])))
    print("Errors:", final_state.get("errors", []))
