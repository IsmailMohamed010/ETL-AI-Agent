import yaml
import pandas as pd

class RuleEngine:
    """
    Deterministic symbolic rule engine.
    Rules are executed in fixed order.
    """

    def __init__(self, rule_file):
        with open(rule_file, "r") as f:
            self.rules = yaml.safe_load(f)["rules"]

        # fixed order execution
        self.rules = sorted(self.rules, key=lambda r: r["priority"])

        self.audit_log = []

    def apply(self, df, signals):
        for rule in self.rules:
            df = self._evaluate_and_apply(df, rule, signals)
        return df

    def _evaluate_and_apply(self, df, rule, signals):
        condition = rule["condition"]
        action = rule["action"]["type"]

        # ---- Explicit deterministic conditions ----

        if condition["type"] == "null_ratio_gt":
            threshold = condition["threshold"]
            col_null = df.isna().mean()

            cols_to_drop = col_null[col_null > threshold].index.tolist()

            if cols_to_drop:
                df = df.drop(columns=cols_to_drop)
                self._log(rule["id"], f"Dropped columns: {cols_to_drop}")

        elif condition["type"] == "ml_signal_gt":
            signal_name = condition["signal"]
            threshold = condition["threshold"]

            if signals.get(signal_name, 0) > threshold:
                if action == "alert":
                    self._log(rule["id"], "High ML risk detected")

        return df

    def _log(self, rule_id, message):
        self.audit_log.append({
            "rule_id": rule_id,
            "message": message
        })
