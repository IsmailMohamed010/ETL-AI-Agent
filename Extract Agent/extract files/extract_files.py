from agentstate import AgentState
import pandas as pd
import requests
import os
import sqlite3


def extract_files_node(state: AgentState) -> AgentState:
    extracted_data = {}

    for file_meta in state["files"]:
        file_path = file_meta.get("file_path")
        if not file_path or not os.path.exists(file_path):
            extracted_data[file_path or "unknown"] = "❌ File not found"
            continue

        ext = os.path.splitext(file_path)[1][1:].lower()
        try:
            if ext == "csv":
                df = pd.read_csv(file_path)
                extracted_data[os.path.basename(file_path)] = df.to_dict(orient="records")
            elif ext in ["xls", "xlsx"]:
                sheets = pd.read_excel(file_path, sheet_name=None)
                extracted_data[os.path.basename(file_path)] = {k: v.to_dict(orient="records") for k, v in sheets.items()}
            else:
                extracted_data[file_path] = f"⚠️ Unsupported file type: {ext}"
            print(f"✓ Extracted → {file_path}")
        except Exception as e:
            extracted_data[file_path] = f"❌ Error: {e}"

    state["extracted_data"] = extracted_data
    return state
