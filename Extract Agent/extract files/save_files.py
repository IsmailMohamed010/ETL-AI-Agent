from agentstate import AgentState
import pandas as pd
import os
import sqlite3
import json


def save_extracted_result_csv(extracted_data: dict):
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


def save_relations_json(relations: dict, filename="output_relations/relations.json"):
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(relations, f, indent=4)

    print(f"✓ Relations saved → {filename}")