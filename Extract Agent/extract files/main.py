import os
from agentstate import AgentState
from detect_excel_relations import detect_excel_relationships, print_detected_relationships
from save_files import save_extracted_result_db, save_extracted_result_csv, save_relations_json
from extract_files import extract_files_node
from langgraph.graph import StateGraph, END

def save_csv_node(state: AgentState) -> AgentState:
    save_extracted_result_csv(state.get("extracted_data", {}))
    print("✅ Data saved to CSV")
    return state

def save_db_node(state: AgentState) -> AgentState:
    save_extracted_result_db(state.get("extracted_data", {}))
    print("✅ Data saved to DB")
    return state

def save_relations_node(state: AgentState) -> AgentState:
    save_relations_json(state.get("detected_relations", {}))
    print("✅ Relations saved to JSON")
    return state

# ── Load all files from uploads folder ──────────────────────────────────────
uploads_dir = r"C:\Users\Ahmed\ETL-AI-Agent\web\uploads"

files = [
    {"file_path": os.path.join(uploads_dir, f), "doc_type": "file"}
    for f in os.listdir(uploads_dir)
    if os.path.isfile(os.path.join(uploads_dir, f))
]

if not files:
    print("⚠️ No files found in uploads folder. Exiting.")
    exit()

print(f"📂 Found {len(files)} file(s) to process:")
for f in files:
    print(f"   - {f['file_path']}")

# ── Build Graph ──────────────────────────────────────────────────────────────
graph = StateGraph(AgentState)

# Nodes
graph.add_node("extract_files", extract_files_node)
graph.add_node("detect_excel_relationships", detect_excel_relationships)
graph.add_node("print_detected_relationships", print_detected_relationships)
graph.add_node("save_relations_json", save_relations_node)
graph.add_node("save_extracted_result_csv", save_csv_node)
graph.add_node("save_extracted_result_db", save_db_node)

# Edges
graph.set_entry_point("extract_files")
graph.add_edge("extract_files", "detect_excel_relationships")
graph.add_edge("detect_excel_relationships", "print_detected_relationships")
graph.add_edge("print_detected_relationships", "save_relations_json")
graph.add_edge("save_relations_json", "save_extracted_result_csv")
graph.add_edge("save_extracted_result_csv", "save_extracted_result_db")
graph.add_edge("save_extracted_result_db", END)

# ── Run ──────────────────────────────────────────────────────────────────────
state = {"files": files}

app = graph.compile()
result = app.invoke(state)

print("\n✅ Graph execution finished")