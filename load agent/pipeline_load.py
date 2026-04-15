import os
import pandas as pd
import pyodbc


# ======================================================
# 🔹 DB CONNECTION (WINDOWS AUTH - SQL SERVER)
# ======================================================
def get_db_connection():

    server = input("Enter Server Name: ")
    database = input("Enter Database Name: ")

    conn_str = f"""
        DRIVER={{ODBC Driver 17 for SQL Server}};
        SERVER={server};
        DATABASE={database};
        Trusted_Connection=yes;
        TrustServerCertificate=yes;
    """

    return pyodbc.connect(conn_str)


# ======================================================
# 🔹 INIT METADATA TABLE (FIXED)
# ======================================================
def init_metadata(conn):

    cursor = conn.cursor()

    cursor.execute("""
    IF OBJECT_ID('loaded_files', 'U') IS NULL
    BEGIN
        CREATE TABLE loaded_files (
            file_name NVARCHAR(255) PRIMARY KEY
        )
    END
    """)

    conn.commit()
    cursor.close()


# ======================================================
# 🔹 CHECK IF FILE LOADED BEFORE (FIXED ?)
# ======================================================
def is_loaded(conn, file_name):

    cursor = conn.cursor()

    cursor.execute(
        "SELECT file_name FROM loaded_files WHERE file_name = ?",
        (file_name,)
    )

    result = cursor.fetchone()
    cursor.close()

    return result is not None


# ======================================================
# 🔹 REGISTER FILE (FIXED)
# ======================================================
def register_file(conn, file_name):

    cursor = conn.cursor()

    cursor.execute(
        "IF NOT EXISTS (SELECT 1 FROM loaded_files WHERE file_name = ?) "
        "INSERT INTO loaded_files (file_name) VALUES (?)",
        (file_name, file_name)
    )

    conn.commit()
    cursor.close()


# ======================================================
# 🔹 CREATE TABLE (FIXED SQL SERVER SYNTAX)
# ======================================================
def create_table(conn, df, table_name):

    cursor = conn.cursor()

    columns = df.columns.tolist()
    column_defs = [f"[{col}] NVARCHAR(MAX)" for col in columns]

    query = f"""
    IF OBJECT_ID('{table_name}', 'U') IS NULL
    BEGIN
        CREATE TABLE {table_name} (
            {', '.join(column_defs)}
        )
    END
    """

    cursor.execute(query)
    conn.commit()
    cursor.close()


# ======================================================
# 🔹 INSERT DATA (FIXED PLACEHOLDERS)
# ======================================================
def insert_data(conn, df, table_name, mode="overwrite"):

    cursor = conn.cursor()

    columns = df.columns.tolist()

    if mode == "overwrite":
        cursor.execute(f"TRUNCATE TABLE {table_name}")

    columns_sql = ', '.join([f"[{c}]" for c in columns])
    placeholders = ', '.join(['?'] * len(columns))

    insert_query = f"""
        INSERT INTO {table_name} ({columns_sql})
        VALUES ({placeholders})
    """

    # 🚀 FAST INSERT (better than loop)
    cursor.fast_executemany = True
    data = [tuple(row) for _, row in df.iterrows()]
    cursor.executemany(insert_query, data)

    conn.commit()
    cursor.close()


# ======================================================
# 🔹 VIEW TABLE (OPTIONAL)
# ======================================================
def view_table(conn, table_name):

    cursor = conn.cursor()

    cursor.execute(f"SELECT TOP 5 * FROM {table_name}")
    rows = cursor.fetchall()

    columns = [desc[0] for desc in cursor.description]
    df = pd.DataFrame(rows, columns=columns)

    print("\n📊 TABLE:", table_name)
    print(df)

    cursor.close()


# ======================================================
# 🔹 MAIN PIPELINE
# ======================================================
def run():

    folder_path = input("📂 Enter folder path: ").strip()

    if not os.path.exists(folder_path):
        print("❌ Folder not found")
        return

    conn = get_db_connection()

    init_metadata(conn)

    csv_files = [f for f in os.listdir(folder_path) if f.endswith(".csv")]

    if not csv_files:
        print("⚠️ No CSV files found")
        return

    print(f"\n📁 Found files: {csv_files}")

    success, skipped = 0, 0

    for file_name in csv_files:

        file_path = os.path.join(folder_path, file_name)
        table_name = file_name.replace(".csv", "")

        print(f"\n🔄 Processing: {file_name}")

        try:
            df = pd.read_csv(file_path)

            if df.empty:
                print("⚠️ Empty file → skipped")
                continue

            if is_loaded(conn, file_name):

                print("⚠️ Already loaded before")

                choice = input("(o) overwrite / (s) skip / (a) append: ").lower()

                if choice == "s":
                    print("⏭️ Skipped")
                    skipped += 1
                    continue

                elif choice == "o":
                    create_table(conn, df, table_name)
                    insert_data(conn, df, table_name, "overwrite")
                    print("♻️ Overwritten")

                elif choice == "a":
                    create_table(conn, df, table_name)
                    insert_data(conn, df, table_name, "append")
                    print("➕ Appended")

                else:
                    print("❌ Invalid → skipped")
                    skipped += 1
                    continue

            else:
                create_table(conn, df, table_name)
                insert_data(conn, df, table_name)
                register_file(conn, file_name)
                print("✅ Loaded first time")

            success += 1

        except Exception as e:
            print(f"❌ Error: {e}")

    print("\n======================")
    print("📊 LOAD SUMMARY")
    print(f"✅ Loaded: {success}")
    print(f"⏭️ Skipped: {skipped}")
    print("======================")

    conn.close()


# ======================================================
# 🚀 ENTRY POINT
# ======================================================
if __name__ == "__main__":
    run()