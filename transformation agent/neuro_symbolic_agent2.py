"""
Neuro-Symbolic Rule Agent (All-in-One)
-------------------------------------
- Symbolic rules (YAML)
- Neural confidence ranking
- Agent-based safe execution
- Non-blocking fail_pipeline policy
- No data loading

Graduation Project
"""

import yaml
import torch
import torch.nn as nn
import torch.nn.functional as F
import pandas as pd


# =====================================================
# NEURAL COMPONENT (Confidence Estimator)
# =====================================================

class RuleEnhancerNN(nn.Module):
    def __init__(self, input_dim=6):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, 32)
        self.fc2 = nn.Linear(32, 16)
        self.confidence_head = nn.Linear(16, 1)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        confidence = torch.sigmoid(self.confidence_head(x))
        return confidence.item()


# =====================================================
# NEURO-SYMBOLIC DECISION ENGINE
# =====================================================

class NeuroSymbolicRuleEngine:
    def __init__(self, rule_file: str):
        with open(rule_file, "r") as f:
            self.rules = yaml.safe_load(f)["rules"]

        self.nn = RuleEnhancerNN()
        self.nn.eval()

    def _extract_features(self, rule, data_stats):
        """
        Convert rule + dataset metadata → NN features
        """
        return torch.tensor([
            data_stats.get("null_ratio", 0.0),
            data_stats.get("row_count", 1) / 1e6,
            data_stats.get("column_importance", 0.5),
            rule.get("priority", 0) / 100,
            data_stats.get("historical_failure_rate", 0.0),
            hash(rule["category"]) % 10 / 10
        ], dtype=torch.float32)

    def decide(self, data_stats):
        """
        Return ranked rule candidates (agent will apply best ones)
        """
        decisions = []

        for rule in self.rules:
            features = self._extract_features(rule, data_stats)
            confidence = self.nn(features)

            decisions.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "base_action": rule["action"]["type"],
                "confidence": round(confidence, 3),
                "applied": False,
                "reason": "Candidate rule"
            })

        # 🔥 Rank rules by neural usefulness
        decisions.sort(key=lambda x: x["confidence"], reverse=True)
        return decisions


# =====================================================
# EXECUTION ENGINE (SAFE AGENT POLICY)
# =====================================================

class RuleExecutor:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def apply(self, decisions, max_rules=3, min_confidence=0.35):
        """
        Agent applies the BEST rules based on NN confidence.
        Destructive rules (fail_pipeline) are evaluated but skipped.
        """
        applied = 0

        for d in decisions:
            if applied >= max_rules:
                break

            if d["confidence"] < min_confidence:
                continue

            action = d["base_action"]

            # 🚫 Safe policy: never break pipeline automatically
            if action == "fail_pipeline":
                d["applied"] = False
                d["reason"] = "Skipped fail_pipeline (safe execution mode)"
                continue

            # ✅ Apply useful rules
            d["applied"] = True
            d["reason"] = "Applied by agent ranking"

            if action == "drop_column":
                self._drop_high_null_columns()

            elif action == "drop_row":
                self._drop_rows_with_nulls()

            elif action == "normalize_date":
                self._normalize_dates()

            elif action == "derive_column":
                self._derive_columns()

            applied += 1

        return self.df, decisions

    # ---------------- Execution Actions ----------------

    def _drop_high_null_columns(self, threshold=0.6):
        null_ratio = self.df.isna().mean()
        cols = null_ratio[null_ratio > threshold].index.tolist()
        self.df.drop(columns=cols, inplace=True)

    def _drop_rows_with_nulls(self):
        self.df.dropna(inplace=True)

    def _normalize_dates(self):
        for col in self.df.columns:
            if "date" in col.lower():
                self.df[col] = pd.to_datetime(self.df[col], errors="coerce")

    def _derive_columns(self):
        if {"price", "quantity"}.issubset(self.df.columns):
            self.df["total_amount"] = self.df["price"] * self.df["quantity"]


# =====================================================
# AGENT ENTRY POINT (NO DATA LOADING)
# =====================================================

def run_neuro_symbolic_agent(df: pd.DataFrame, data_context: dict, rules_path="rules.yaml"):
    """
    Main agent function:
    - df: DataFrame provided by another agent
    - data_context: metadata extracted by agent
    """

    engine = NeuroSymbolicRuleEngine(rules_path)
    decisions = engine.decide(data_context)

    executor = RuleExecutor(df)
    df, decisions = executor.apply(decisions)

    return df, decisions
