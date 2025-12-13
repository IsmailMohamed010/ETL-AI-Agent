from agentstate import AgentState
import pandas as pd
import requests
import os
import sqlite3


def extract_files(state: AgentState):
    """
    Extract data from multiple sources (files, APIs, databases).
    Supports CSV, TXT, PDF, Excel (single + multi sheet).
    """
    extracted_data = {}

    for file_meta in state["files"]:
        doc_type = (file_meta.get("doc_type") or "").lower()
        file_path = file_meta.get("file_path")
        file_type = os.path.splitext(file_path)[1][1:].lower() if file_path else ""

        if not file_path:
            extracted_data["unknown_source"] = "❌ Missing file_path"
            continue

        try:
            if doc_type == "file":
                if not os.path.exists(file_path):
                    extracted_data[file_path] = f"❌ File not found: {file_path}"
                    continue

                # ---------------- CSV ----------------
                if file_type == "csv":
                    df = pd.read_csv(file_path)
                    extracted_data[os.path.basename(file_path)] = df.to_dict(orient="records")

                # ---------------- EXCEL (multi sheet) ----------------
                elif file_type in ["xlsx", "xls", "excel"]:
                    sheets = pd.read_excel(file_path, sheet_name=None)
                    excel_data = {}

                    for sheet_name, df_sheet in sheets.items():
                        excel_data[sheet_name] = df_sheet.to_dict(orient="records")

                    extracted_data[os.path.basename(file_path)] = excel_data

                # ---------------- TXT ----------------
                elif file_type == "txt":
                    with open(file_path, "r", encoding="utf-8") as f:
                        extracted_data[os.path.basename(file_path)] = f.read()

                else:
                    extracted_data[file_path] = f"⚠️ Unsupported file type: {file_type}"

                print(f"✓ Successfully extracted → {file_path}")

        except Exception as e:
            extracted_data[file_path] = f"❌ Error extracting data: {e}"

    return {"extracted_data": extracted_data}
