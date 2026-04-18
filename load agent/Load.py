import os
import sys
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import pyodbc


# ======================================================
# ⚙️  FIXED CONFIGURATION
# ======================================================

FOLDER_PATH = r"F:\last_part1\Grad_project\out_transformation"

DB_SERVER   = r"DESKTOP-2Q8MF7K\SQLEXPRESS"
DB_NAME     = "Test_load"
DB_USER     = ""          # leave empty → Windows Auth
DB_PASSWORD = ""          # leave empty → Windows Auth

# ======================================================
# 📋 LOGGING SETUP
# ======================================================

LOG_PATH = os.path.join(os.path.dirname(__file__), "load_log.txt")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ======================================================
# 🔹 DB CONNECTION
#    Uses Windows Auth when user/password are empty,
#    SQL Server Auth otherwise.
# ======================================================

def get_connection() -> pyodbc.Connection:

    if DB_USER and DB_PASSWORD:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_SERVER};"
            f"DATABASE={DB_NAME};"
            f"UID={DB_USER};"
            f"PWD={DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )
        auth_mode = "SQL Server Auth"
    else:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_SERVER};"
            f"DATABASE={DB_NAME};"
            f"Trusted_Connection=yes;"
            f"TrustServerCertificate=yes;"
        )
        auth_mode = "Windows Auth"

    log.info(f"Connecting → server={DB_SERVER}  db={DB_NAME}  mode={auth_mode}")

    try:
        conn = pyodbc.connect(conn_str, autocommit=False)
        log.info("✅ Connection established.")
        return conn
    except pyodbc.Error as exc:
        log.error(f"❌ Connection failed: {exc}")
        raise


# ======================================================
# 🔹 METADATA TABLE
# ======================================================

def init_metadata(conn: pyodbc.Connection) -> None:
    """
    Create loaded_files if it doesn't exist.
    If it already exists from an older version (only has file_name),
    auto-migrate by adding the missing columns — no data is lost.
    """
    with conn.cursor() as cur:

        # 1. Create table if completely absent
        cur.execute("""
            IF OBJECT_ID('loaded_files', 'U') IS NULL
            CREATE TABLE loaded_files (
                file_name       NVARCHAR(255) PRIMARY KEY,
                loaded_at       DATETIME      NOT NULL DEFAULT GETDATE(),
                row_count       INT,
                last_action     NVARCHAR(50)
            )
        """)
        conn.commit()

        # 2. Auto-migrate: add any columns that may be missing
        #    (handles the case where the old 1-column table already exists)
        migrations = [
            ("loaded_at",   "ALTER TABLE loaded_files ADD loaded_at   DATETIME     NOT NULL DEFAULT GETDATE()"),
            ("row_count",   "ALTER TABLE loaded_files ADD row_count   INT"),
            ("last_action", "ALTER TABLE loaded_files ADD last_action NVARCHAR(50)"),
        ]

        for col_name, alter_sql in migrations:
            cur.execute("""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'loaded_files' AND COLUMN_NAME = ?
                )
                EXEC(?)
            """, (col_name, alter_sql))

        conn.commit()

    log.info("Metadata table ready (schema up-to-date).")


def is_loaded(conn: pyodbc.Connection, file_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM loaded_files WHERE file_name = ?", (file_name,)
        )
        return cur.fetchone() is not None


def register_file(
    conn: pyodbc.Connection,
    file_name: str,
    row_count: int,
    action: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            MERGE loaded_files AS target
            USING (SELECT ? AS file_name) AS src
                ON target.file_name = src.file_name
            WHEN MATCHED THEN
                UPDATE SET loaded_at   = GETDATE(),
                           row_count   = ?,
                           last_action = ?
            WHEN NOT MATCHED THEN
                INSERT (file_name, loaded_at, row_count, last_action)
                VALUES (?, GETDATE(), ?, ?);
        """, (file_name, row_count, action, file_name, row_count, action))
        conn.commit()


# ======================================================
# 🔹 SCHEMA HELPERS
# ======================================================

_TYPE_MAP = {
    "int64":   "BIGINT",
    "int32":   "INT",
    "float64": "FLOAT",
    "float32":  "FLOAT",
    "bool":    "BIT",
    "datetime64[ns]": "DATETIME2",
    "object":  "NVARCHAR(MAX)",
}

def _sql_type(dtype) -> str:
    return _TYPE_MAP.get(str(dtype), "NVARCHAR(MAX)")


def _safe_table(name: str) -> str:
    """Strip path artefacts and sanitize for use as a SQL identifier."""
    base = os.path.splitext(os.path.basename(name))[0]
    # replace anything that is not alphanumeric or underscore
    safe = "".join(c if c.isalnum() or c == "_" else "_" for c in base)
    return safe


def create_table_if_missing(
    conn: pyodbc.Connection,
    df: pd.DataFrame,
    table_name: str,
) -> None:
    col_defs = ",\n            ".join(
        f"[{col}] {_sql_type(df[col].dtype)}" for col in df.columns
    )
    sql = f"""
        IF OBJECT_ID('{table_name}', 'U') IS NULL
        BEGIN
            CREATE TABLE [{table_name}] (
                {col_defs}
            )
        END
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


# ======================================================
# 🔹 DATA INSERT
# ======================================================

def _coerce_row(row) -> tuple:
    """Convert numpy/pandas types to Python natives for pyodbc."""
    result = []
    for v in row:
        if pd.isna(v):
            result.append(None)
        elif isinstance(v, (int, float, str, bool, type(None))):
            result.append(v)
        else:
            result.append(str(v))
    return tuple(result)


def insert_data(
    conn: pyodbc.Connection,
    df: pd.DataFrame,
    table_name: str,
    mode: str = "overwrite",
) -> int:
    """
    Insert DataFrame into SQL Server table.
    mode: 'overwrite' (TRUNCATE first) | 'append'
    Returns number of rows inserted.
    """
    columns_sql   = ", ".join(f"[{c}]" for c in df.columns)
    placeholders  = ", ".join(["?"] * len(df.columns))
    insert_sql    = f"INSERT INTO [{table_name}] ({columns_sql}) VALUES ({placeholders})"

    data = [_coerce_row(row) for _, row in df.iterrows()]

    with conn.cursor() as cur:
        if mode == "overwrite":
            cur.execute(f"TRUNCATE TABLE [{table_name}]")
            log.info(f"  Table [{table_name}] truncated.")

        cur.fast_executemany = True
        cur.executemany(insert_sql, data)
        conn.commit()

    return len(data)


# ======================================================
# 🔹 PREVIEW
# ======================================================

def preview_table(conn: pyodbc.Connection, table_name: str, rows: int = 5) -> None:
    with conn.cursor() as cur:
        cur.execute(f"SELECT TOP {rows} * FROM [{table_name}]")
        cols = [d[0] for d in cur.description]
        # Convert pyodbc Row objects → plain tuples so pandas unpacks correctly
        data = [tuple(row) for row in cur.fetchall()]
    df = pd.DataFrame(data, columns=cols)
    log.info(f"\n{'─'*60}\n  Preview → [{table_name}]\n{'─'*60}\n{df.to_string(index=False)}\n{'─'*60}")


# ======================================================
# 🔹 USER PROMPT (SINGLE-CHAR, VALIDATED)
# ======================================================

def ask_mode(file_name: str) -> Optional[str]:
    """Return 'overwrite' | 'append' | None (skip)."""
    print(f"\n  ⚠️  '{file_name}' was loaded before.")
    print("      [o] Overwrite    [a] Append    [s] Skip")

    while True:
        choice = input("  Your choice: ").strip().lower()
        if choice == "o":
            return "overwrite"
        if choice == "a":
            return "append"
        if choice == "s":
            return None
        print("  ❌ Invalid — please enter o / a / s")


# ======================================================
# 🔹 MAIN PIPELINE
# ======================================================

def run() -> None:

    log.info("=" * 60)
    log.info("  CSV → SQL Server Loader  |  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("=" * 60)

    # ── Validate folder ──
    if not os.path.exists(FOLDER_PATH):
        log.error(f"❌ Folder not found: {FOLDER_PATH}")
        sys.exit(1)

    # ── Collect CSV files ──
    csv_files = [
        f for f in sorted(os.listdir(FOLDER_PATH))
        if f.lower().endswith(".csv")
    ]

    if not csv_files:
        log.warning("⚠️  No CSV files found in folder.")
        return

    log.info(f"📂 Folder : {FOLDER_PATH}")
    log.info(f"📋 Files  : {csv_files}\n")

    # ── Connect ──
    conn = get_connection()
    init_metadata(conn)

    success, skipped, failed = 0, 0, 0

    for file_name in csv_files:

        file_path  = os.path.join(FOLDER_PATH, file_name)
        table_name = _safe_table(file_name)

        log.info(f"🔄 [{file_name}]  →  table [{table_name}]")

        try:
            df = pd.read_csv(file_path)

            if df.empty:
                log.warning("  ⚠️  File is empty — skipped.")
                skipped += 1
                continue

            log.info(f"  Rows: {len(df):,}   Columns: {list(df.columns)}")

            # ── Decide mode ──
            if is_loaded(conn, file_name):
                mode = ask_mode(file_name)

                if mode is None:
                    log.info("  ⏭️  Skipped by user.")
                    skipped += 1
                    continue
            else:
                mode = "overwrite"   # first-time load → fresh insert

            # ── Load ──
            create_table_if_missing(conn, df, table_name)
            rows_inserted = insert_data(conn, df, table_name, mode)
            register_file(conn, file_name, rows_inserted, mode)

            action_label = "♻️  Overwritten" if mode == "overwrite" else "➕ Appended"
            log.info(f"  {action_label} — {rows_inserted:,} rows inserted.")

            preview_table(conn, table_name)

            success += 1

        except Exception as exc:
            log.exception(f"  ❌ Error processing '{file_name}': {exc}")
            failed += 1
            # Roll back any partial work for this file
            try:
                conn.rollback()
            except Exception:
                pass

    # ── Summary ──
    log.info("\n" + "=" * 40)
    log.info("  📊 LOAD SUMMARY")
    log.info(f"  ✅ Loaded  : {success}")
    log.info(f"  ⏭️  Skipped : {skipped}")
    log.info(f"  ❌ Failed  : {failed}")
    log.info("=" * 40)
    log.info(f"  Full log  : {LOG_PATH}")

    conn.close()


# ======================================================
# 🚀 ENTRY POINT
# ======================================================

if __name__ == "__main__":
    run()