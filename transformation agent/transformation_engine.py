import pandas as pd
import numpy as np
import yaml
import json
from scipy.stats import skew
from datetime import datetime
from typing import Dict, List


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

    @staticmethod
    def execute(df: pd.DataFrame, actions: List[Dict]):

        applied_actions = []

        for action in actions:

            if action["action"] == "drop_column":

                col = action["column"]

                if col in df.columns:
                    df = df.drop(columns=[col])
                    applied_actions.append(action)

            elif action["action"] == "alert":

                applied_actions.append(action)

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
        transformed_df, applied_actions = Executor.execute(df, actions)

        # Step 5: Audit Logging
        AuditLogger.log(applied_actions)

        # Save transformed data
        transformed_df.to_csv(output_path, index=False)

        print("Pipeline completed successfully.")
        print("Profile:", profile)
        print("Signals:", signals)
        print("Applied Actions:", applied_actions)


# ============================================================
# SMART PRODUCTION RUNNER
# ============================================================

import os


if __name__ == "__main__":

    DATA_FOLDER = "/content"  # change if needed
    RULES_PATH = "rules.yaml"

    engine = TransformationEngine(RULES_PATH)

    # Automatically detect all CSV files
    csv_files = [
        f for f in os.listdir(DATA_FOLDER)
        if f.endswith(".csv") and not f.startswith("transformed_")
    ]

    if not csv_files:
        print("No CSV files found.")
    else:
        print(f"Found {len(csv_files)} dataset(s):", csv_files)

    for file_name in csv_files:

        input_path = os.path.join(DATA_FOLDER, file_name)

        output_name = f"transformed_{file_name}"
        output_path = os.path.join(DATA_FOLDER, output_name)

        print(f"\nProcessing: {file_name}")

        engine.run(input_path, output_path)

    print("\nAll datasets processed successfully.")