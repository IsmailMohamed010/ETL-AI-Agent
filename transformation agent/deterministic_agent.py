import yaml
import pandas as pd
import numpy as np


# =====================================================
# DETERMINISTIC RULE SCORING ENGINE
# =====================================================

class DeterministicRuleEngine:
    def __init__(self, rule_file: str):
        with open(rule_file, "r") as f:
            self.rules = yaml.safe_load(f)["rules"]

    # -------------------------------------------------
    # Dataset-Level Feature Extraction (ALL COLUMNS)
    # -------------------------------------------------

    def extract_dataset_stats(self, df: pd.DataFrame):

        stats = {}

        stats["row_count"] = len(df)
        stats["column_count"] = df.shape[1]

        # Global null ratio
        stats["global_null_ratio"] = df.isna().mean().mean()

        # Per-column null ratio
        stats["column_null_ratios"] = df.isna().mean().to_dict()

        # Numeric columns
        numeric_df = df.select_dtypes(include=np.number)

        if not numeric_df.empty:
            stats["skewness"] = numeric_df.skew().mean()
        else:
            stats["skewness"] = 0

        # Date columns detection
        stats["date_columns"] = [
            col for col in df.columns if "date" in col.lower()
        ]

        return stats

    # -------------------------------------------------
    # Deterministic Rule Scoring
    # -------------------------------------------------

    def score_rule(self, rule, stats):

        score = 0

        action = rule["action"]["type"]

        # Rule: Drop High Null Columns
        if action == "drop_column":
            high_null_cols = [
                col for col, ratio in stats["column_null_ratios"].items()
                if ratio > 0.6
            ]
            score = len(high_null_cols)

        # Rule: Drop Rows
        elif action == "drop_row":
            score = stats["global_null_ratio"]

        # Rule: Normalize Dates
        elif action == "normalize_date":
            score = len(stats["date_columns"])

        # Rule: Derive Column
        elif action == "derive_column":
            score = 1  # deterministic small score

        # Rule: Fail Pipeline
        elif action == "fail_pipeline":
            score = 0  # never auto-prioritize

        return round(score, 4)

    # -------------------------------------------------
    # Decision Phase
    # -------------------------------------------------

    def decide(self, df: pd.DataFrame):

        stats = self.extract_dataset_stats(df)

        decisions = []

        for rule in self.rules:
            score = self.score_rule(rule, stats)

            decisions.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "base_action": rule["action"]["type"],
                "confidence": score,
                "applied": False,
                "reason": "Deterministic scoring"
            })

        # Sort by score descending
        decisions.sort(key=lambda x: x["confidence"], reverse=True)

        return decisions


# =====================================================
# EXECUTION ENGINE (SAFE + DETERMINISTIC)
# =====================================================

class RuleExecutor:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def apply(self, decisions, max_rules=3):

        applied = 0

        for d in decisions:
            if applied >= max_rules:
                break

            if d["confidence"] <= 0:
                continue

            action = d["base_action"]

            if action == "fail_pipeline":
                continue

            d["applied"] = True
            d["reason"] = "Applied deterministically"

            if action == "drop_column":
                self._drop_high_null_columns()

            elif action == "drop_row":
                self.df.dropna(inplace=True)

            elif action == "normalize_date":
                self._normalize_dates()

            elif action == "derive_column":
                if {"price", "quantity"}.issubset(self.df.columns):
                    self.df["total_amount"] = (
                        self.df["price"] * self.df["quantity"]
                    )

            applied += 1

        return self.df, decisions

    def _drop_high_null_columns(self, threshold=0.6):
        null_ratio = self.df.isna().mean()
        cols = null_ratio[null_ratio > threshold].index.tolist()
        self.df.drop(columns=cols, inplace=True)

    def _normalize_dates(self):
        for col in self.df.columns:
            if "date" in col.lower():
                self.df[col] = pd.to_datetime(self.df[col], errors="coerce")


# =====================================================
# ENTRY POINT
# =====================================================

def run_neuro_symbolic_agent(df: pd.DataFrame, rules_path="rules.yaml"):

    engine = DeterministicRuleEngine(rules_path)
    decisions = engine.decide(df)

    executor = RuleExecutor(df)
    df, decisions = executor.apply(decisions)

    return df, decisions