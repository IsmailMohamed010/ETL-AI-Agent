import pandas as pd
import numpy as np
import yaml
import json
from scipy.stats import skew
from datetime import datetime
from typing import Dict, List
import os


# ============================================================
# ⚙️  FIXED CONFIGURATION (no CLI args needed)
# ============================================================

INPUT_FOLDER  = r"F:\last_part1\Grad_project\out_extract"
OUTPUT_FOLDER = r"F:\last_part1\Grad_project\out_transformation"
RULES_PATH    = r"rules.yaml"


# ============================================================
# 1️⃣ DATASET PROFILER (DETERMINISTIC)
# ============================================================

class DatasetProfiler:

    @staticmethod
    def profile(df: pd.DataFrame) -> Dict:
        profile = {}

        profile["row_count"] = int(df.shape[0])
        profile["column_count"] = int(df.shape[1])

        total_cells = df.size
        total_nulls = df.isnull().sum().sum()
        profile["global_null_ratio"] = float(total_nulls / total_cells)

        profile["column_null_ratios"] = (
            df.isnull().mean().to_dict()
        )

        numeric_cols = df.select_dtypes(include=np.number).columns
        profile["numeric_column_ratio"] = float(
            len(numeric_cols) / df.shape[1]
        )

        skewness = {}
        for col in numeric_cols:
            if df[col].dropna().shape[0] > 0:
                skewness[col] = float(skew(df[col].dropna()))
            else:
                skewness[col] = 0.0

        profile["skewness"] = skewness

        return profile


# ============================================================
# 2️⃣ NEURAL SIGNAL GENERATOR (ADVISORY ONLY)
# ============================================================

class NeuralSignalGenerator:
    """
    Neural component:
    - Does NOT modify data
    - Does NOT rank rules
    - Does NOT skip rules
    - Only produces signals
    """

    @staticmethod
    def generate(profile: Dict) -> Dict:

        # Deterministic ML-style scoring
        risk_score = (
            profile["global_null_ratio"] * 0.6 +
            profile["numeric_column_ratio"] * 0.2 +
            (len(profile["skewness"]) > 0) * 0.2
        )

        risk_score = max(0.0, min(1.0, risk_score))

        signals = {
            "ml_risk_score": float(risk_score),
            "avg_null_ratio": float(profile["global_null_ratio"]),
            "high_skew_columns": [
                col for col, val in profile["skewness"].items()
                if abs(val) > 2
            ]
        }

        return signals


# ============================================================
# 3️⃣ DETERMINISTIC RULE ENGINE
# ============================================================

class RuleEngine:

    def __init__(self, rules_path: str):

        with open(rules_path, "r") as f:
            config = yaml.safe_load(f)

        # Strict deterministic priority ordering
        self.rules = sorted(
            config["rules"],
            key=lambda x: x["priority"]
        )

    def evaluate(self, df: pd.DataFrame, profile: Dict, signals: Dict) -> List[Dict]:

        actions = []

        for rule in self.rules:

            rule_id = rule["id"]
            condition = rule["condition"]

            # COLUMN NULL RATIO CONDITION
            if condition["type"] == "column_null_ratio":

                for col, ratio in profile["column_null_ratios"].items():

                    if self._compare(
                        ratio,
                        condition["operator"],
                        condition["value"]
                    ):
                        actions.append({
                            "rule_id": rule_id,
                            "action": rule["action"],
                            "column": col
                        })

            # ML SIGNAL CONDITION
            elif condition["type"] == "ml_risk_score":

                if self._compare(
                    signals["ml_risk_score"],
                    condition["operator"],
                    condition["value"]
                ):
                    actions.append({
                        "rule_id": rule_id,
                        "action": rule["action"],
                        "column": None
                    })

        return actions

    @staticmethod
    def _compare(a, operator, b):

        if operator == ">":
            return a > b
        if operator == "<":
            return a < b
        if operator == ">=":
            return a >= b
        if operator == "<=":
            return a <= b
        if operator == "==":
            return a == b
        if operator == "!=":
            return a != b

        raise ValueError(f"Unsupported operator {operator}")


# ============================================================
# 4️⃣ EXECUTION ENGINE
# ============================================================

class Executor:

    # ----------------------------------------------------------
    # DATE / TIME HANDLER
    # ----------------------------------------------------------
    @staticmethod
    def _handle_datetime_columns(df: pd.DataFrame, applied_actions: List[Dict]):
        """
        Auto-detects datetime columns in two ways:
          1. Columns already parsed as datetime64 dtype by pandas.
          2. Object/string columns whose names contain common datetime
             keywords (date, time, datetime, timestamp, created, updated,
             modified, at, on, day, month, year).

        For each detected column the method:
          - Parses the column with pd.to_datetime (errors='coerce').
          - Extracts: _year, _month, _day, _hour, _minute, _dayofweek,
            _is_weekend as new integer columns.
          - Drops the original raw string column.
          - Records the transformation in applied_actions.
        """

        DATETIME_KEYWORDS = {
            "date", "time", "datetime", "timestamp",
            "created", "updated", "modified",
            "at", "on", "day", "month", "year"
        }

        datetime_cols = []

        for col in df.columns:
            # Already a datetime dtype
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                datetime_cols.append(col)
                continue

            # String/object column whose name hints at datetime
            if pd.api.types.is_object_dtype(df[col]):
                col_lower = col.lower().replace("_", " ").replace("-", " ")
                if any(kw in col_lower.split() for kw in DATETIME_KEYWORDS):
                    datetime_cols.append(col)

        for col in datetime_cols:
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")

                # Skip if everything failed to parse (all NaT)
                if parsed.isna().all():
                    print(f"  ⚠️  Column '{col}' detected as datetime but could not be parsed — skipped.")
                    continue

                prefix = col  # keep original name as prefix

                df[f"{prefix}_year"]      = parsed.dt.year.astype("Int64")
                df[f"{prefix}_month"]     = parsed.dt.month.astype("Int64")
                df[f"{prefix}_day"]       = parsed.dt.day.astype("Int64")
                df[f"{prefix}_hour"]      = parsed.dt.hour.astype("Int64")
                df[f"{prefix}_minute"]    = parsed.dt.minute.astype("Int64")
                df[f"{prefix}_dayofweek"] = parsed.dt.dayofweek.astype("Int64")   # 0=Mon … 6=Sun
                df[f"{prefix}_is_weekend"] = parsed.dt.dayofweek.isin([5, 6]).astype("Int64")

                df = df.drop(columns=[col])

                applied_actions.append({
                    "rule_id": "datetime_extraction",
                    "action": "extract_datetime_features",
                    "column": col,
                    "extracted_features": [
                        f"{prefix}_year", f"{prefix}_month", f"{prefix}_day",
                        f"{prefix}_hour", f"{prefix}_minute",
                        f"{prefix}_dayofweek", f"{prefix}_is_weekend"
                    ],
                    "timestamp": datetime.utcnow().isoformat()
                })

                print(f"  📅 DateTime extracted: '{col}' → 7 feature columns")

            except Exception as e:
                print(f"  ⚠️  Could not process datetime column '{col}': {e}")

        return df

    # ----------------------------------------------------------
    # MAIN EXECUTE
    # ----------------------------------------------------------
    @staticmethod
    def execute(df: pd.DataFrame, actions: List[Dict], profile: Dict):

        applied_actions = []

        # ==========================
        # 0. HANDLE DATE / TIME COLUMNS  ← NEW
        # ==========================
        df = Executor._handle_datetime_columns(df, applied_actions)

        # ==========================
        # 1. HANDLE SMALL NULL % (DROP ROWS)
        # ==========================
        if profile["global_null_ratio"] < 0.02:  # 2% threshold

            before_rows = df.shape[0]
            df = df.dropna()
            after_rows = df.shape[0]

            applied_actions.append({
                "rule_id": "drop_small_nulls",
                "action": "drop_rows",
                "dropped_rows": before_rows - after_rows
            })

        # ==========================
        # 2. APPLY COLUMN ACTIONS
        # ==========================
        for action in actions:

            col = action.get("column")

            if col not in df.columns:
                continue

            # DROP COLUMN
            if action["action"] == "drop_column":

                df = df.drop(columns=[col])
                applied_actions.append(action)

            # FILL WITH MEAN
            elif action["action"] == "fill_mean":

                if pd.api.types.is_numeric_dtype(df[col]):
                    val = df[col].mean()
                    df[col] = df[col].fillna(val)

                    applied_actions.append({**action, "value": float(val)})

            # FILL WITH MEDIAN (NEW)
            elif action["action"] == "fill_median":

                if pd.api.types.is_numeric_dtype(df[col]):
                    val = df[col].median()
                    df[col] = df[col].fillna(val)

                    applied_actions.append({**action, "value": float(val)})

            # FILL WITH MODE
            elif action["action"] == "fill_mode":

                val = df[col].mode()
                if not val.empty:
                    df[col] = df[col].fillna(val[0])

                    applied_actions.append({**action, "value": str(val[0])})

            # ALERT
            elif action["action"] == "alert":
                applied_actions.append(action)

        # ==========================
        # 3. ROUND NUMERIC COLUMNS TO 2 DECIMAL PLACES  ← UPDATED
        # ==========================
        numeric_cols = df.select_dtypes(include="number").columns
        df[numeric_cols] = df[numeric_cols].round(2)

        applied_actions.append({
            "rule_id": "rounding",
            "action": "round_numeric",
            "decimals": 2          # ← changed from 3 to 2
        })

        return df, applied_actions


# ============================================================
# 5️⃣ AUDIT LOGGER
# ============================================================

class AuditLogger:

    @staticmethod
    def log(applied_actions: List[Dict], output_path="audit_log.json"):

        logs = []

        for action in applied_actions:
            logs.append({
                "rule_id": action["rule_id"],
                "action": action["action"],
                "column": action.get("column"),
                "timestamp": datetime.utcnow().isoformat()
            })

        with open(output_path, "w") as f:
            json.dump(logs, f, indent=4)


# ============================================================
# 6️⃣ PIPELINE ORCHESTRATOR
# ============================================================

class TransformationEngine:

    def __init__(self, rules_path: str):
        self.rules_path = rules_path

    def run(self, input_path: str, output_path="transformed_data.csv"):

        # Load raw data
        df = pd.read_csv(input_path)

        # Step 1: Profile
        profile = DatasetProfiler.profile(df)

        # Step 2: Neural Advisory Signals
        signals = NeuralSignalGenerator.generate(profile)

        # Step 3: Deterministic Rule Evaluation
        rule_engine = RuleEngine(self.rules_path)
        actions = rule_engine.evaluate(df, profile, signals)

        # Step 4: Execution
        transformed_df, applied_actions = Executor.execute(df, actions, profile)

        # Step 5: Audit Logging
        AuditLogger.log(applied_actions)

        # Save transformed data
        transformed_df.to_csv(output_path, index=False)

        print("Pipeline completed successfully.")
        print("Profile:", profile)
        print("Signals:", signals)
        print("Applied Actions:", applied_actions)


# ============================================================
# SMART PRODUCTION RUNNER  (fixed paths — no CLI args needed)
# ============================================================

if __name__ == "__main__":

    # ==============================
    # VALIDATION
    # ==============================
    if not os.path.exists(INPUT_FOLDER):
        raise ValueError(f"Input folder does not exist: {INPUT_FOLDER}")

    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"Created output folder: {OUTPUT_FOLDER}")

    # ==============================
    # ENGINE INIT
    # ==============================
    engine = TransformationEngine(RULES_PATH)

    # ==============================
    # AUTO DETECT ONLY NEW FILES
    # ==============================
    csv_files = []

    input_files  = os.listdir(INPUT_FOLDER)
    output_files = os.listdir(OUTPUT_FOLDER)

    for file_name in input_files:

        if not file_name.endswith(".csv"):
            continue

        # Skip already transformed files in input
        if file_name.startswith("transformed_"):
            continue

        transformed_name = f"transformed_{file_name}"

        # 🔥 Skip if already transformed exists in OUTPUT folder
        if transformed_name in output_files:
            print(f"⏭️  Skipping (already transformed): {file_name}")
            continue

        csv_files.append(file_name)

    # ==============================
    # CHECK IF ANY FILES LEFT
    # ==============================
    if not csv_files:
        print("✅ All files are already transformed.")
        exit()

    print(f"\n📂 Files to transform: {csv_files}")

    # ==============================
    # PROCESS EACH FILE
    # ==============================
    for file_name in csv_files:

        input_path = os.path.join(INPUT_FOLDER, file_name)

        output_name = f"transformed_{file_name}"
        output_path = os.path.join(OUTPUT_FOLDER, output_name)

        print(f"\n🔄 Processing: {file_name}")

        engine.run(input_path, output_path)

    print("\n🚀 New datasets processed successfully.")