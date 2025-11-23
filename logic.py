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




from typing import Any


def save_extracted_result(extracted_data: dict):
    """
    Single function:
    - Saves all files inside 'output_saved/' folder
    - CSV saved as CSV
    - Excel saved as folder (each sheet as CSV)
    - TXT saved normally
    """

    BASE_OUTPUT = "output_saved_csv"

    # Create base folder if not exists
    if not os.path.exists(BASE_OUTPUT):
        os.makedirs(BASE_OUTPUT)

    saved_files = []

    for file_name, content in extracted_data.items():

        # Skip errors
        if isinstance(content, str) and content.startswith("❌"):
            print(f"⛔ Skipping {file_name} due to extraction error")
            continue

        # detect extension
        ext = os.path.splitext(file_name)[1].lower().replace(".", "")

        try:
            # ------------------------ CSV ------------------------
            if ext == "csv":
                output_path = os.path.join(BASE_OUTPUT, file_name)
                df = pd.DataFrame(content)
                df.to_csv(output_path, index=False)

                print(f"✓ CSV saved → {output_path}")
                saved_files.append(output_path)

            # -------------------- EXCEL MULTI SHEET --------------------
            elif ext in ["xlsx", "xls", "excel"]:

                folder_name = file_name.replace("." + ext, "")
                folder_path = os.path.join(BASE_OUTPUT, folder_name)

                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)

                for sheet_name, rows in content.items():
                    df = pd.DataFrame(rows)

                    safe_name = sheet_name.replace("/", "_").replace("\\", "_")
                    csv_output = os.path.join(folder_path, f"{safe_name}.csv")

                    df.to_csv(csv_output, index=False)
                    print(f"✓ Sheet saved → {csv_output}")

                saved_files.append(folder_path)

            # ------------------------ TXT ------------------------
            elif ext == "txt":
                output_path = os.path.join(BASE_OUTPUT, file_name)

                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(content)

                print(f"✓ TXT saved → {output_path}")
                saved_files.append(output_path)

            # --------------------- Unsupported ---------------------
            else:
                print(f"⚠️ Unsupported file type: {ext}")

        except Exception as e:
            print(f"❌ Failed to save {file_name}: {e}")

    return {"saved_files": saved_files}




def save_extracted_result_db(extracted_data: dict):
    """
    Single function:
    - Saves all files into SQLite DBs inside 'output_saved/' folder
    - CSV saved as table in DB
    - Excel multi-sheet saved as tables in DB
    - TXT saved as table with one column
    """

    BASE_OUTPUT = "output_saved_database"

    if not os.path.exists(BASE_OUTPUT):
        os.makedirs(BASE_OUTPUT)

    saved_files = []

    for file_name, content in extracted_data.items():

        # Skip errors
        if isinstance(content, str) and content.startswith("❌"):
            print(f"⛔ Skipping {file_name} due to extraction error")
            continue

        # detect extension
        ext = os.path.splitext(file_name)[1].lower().replace(".", "")

        try:
            if ext in ["csv", "txt", "xlsx", "xls", "excel"]:

                # DB path
                db_name = os.path.splitext(file_name)[0] + ".db"
                db_path = os.path.join(BASE_OUTPUT, db_name)

                conn = sqlite3.connect(db_path)

                # ------------------------ CSV ------------------------
                if ext == "csv":
                    df = pd.DataFrame(content)
                    df.to_sql("data", conn, if_exists="replace", index=False)
                    print(f"✓ CSV saved to DB → {db_path} (table: data)")

                # -------------------- TXT ------------------------
                elif ext == "txt":
                    df = pd.DataFrame({"text": [content]})
                    df.to_sql("data", conn, if_exists="replace", index=False)
                    print(f"✓ TXT saved to DB → {db_path} (table: data)")

                # -------------------- EXCEL MULTI SHEET --------------------
                elif ext in ["xlsx", "xls", "excel"]:
                    for sheet_name, rows in content.items():
                        df = pd.DataFrame(rows)
                        safe_name = sheet_name.replace("/", "_").replace("\\", "_")
                        df.to_sql(safe_name, conn, if_exists="replace", index=False)
                        print(f"✓ Sheet saved → {db_path} (table: {safe_name})")

                conn.close()
                saved_files.append(db_path)

            else:
                print(f"⚠️ Unsupported file type: {ext}")

        except Exception as e:
            print(f"❌ Failed to save {file_name}: {e}")

    return {"saved_files": saved_files}