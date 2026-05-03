from agentstate import AgentState
import pandas as pd
from itertools import combinations

def detect_excel_relationships(state: AgentState) -> AgentState:
    extracted = state.get("extracted_data")
    if not extracted:
        state["detected_relations"] = None
        return state

    relations = {}

    def uniqueness_ratio(values):
        s = pd.Series(values).dropna()
        return s.nunique() / len(s) if len(s) else 0

    def overlap_ratio(v1, v2):
        s1, s2 = set(v1), set(v2)
        if not s1 or not s2:
            return 0
        return len(s1 & s2) / min(len(s1), len(s2))

    for file_name, content in extracted.items():
        if not isinstance(content, dict):
            continue  # not Excel

        sheets = {k: pd.DataFrame(v) for k, v in content.items()}
        file_relations = []

        for (s1, df1), (s2, df2) in combinations(sheets.items(), 2):
            for c1 in df1.columns:
                for c2 in df2.columns:
                    v1 = df1[c1].dropna().tolist()
                    v2 = df2[c2].dropna().tolist()

                    if not v1 or not v2:
                        continue
                    if df1[c1].dtype != df2[c2].dtype:
                        continue

                    overlap = overlap_ratio(v1, v2)
                    if overlap < 0.7:
                        continue

                    u1 = uniqueness_ratio(v1)
                    u2 = uniqueness_ratio(v2)

                    if u1 > u2:
                        file_relations.append({
                            "from_sheet": s1,
                            "to_sheet": s2,
                            "from_key": c1,
                            "to_key": c2,
                            "relation": "one-to-many",
                            "confidence": round(overlap, 2)
                        })
                    else:
                        file_relations.append({
                            "from_sheet": s2,
                            "to_sheet": s1,
                            "from_key": c2,
                            "to_key": c1,
                            "relation": "one-to-many",
                            "confidence": round(overlap, 2)
                        })

        if file_relations:
            relations[file_name] = file_relations

    state["detected_relations"] = relations
    return state


def print_detected_relationships(state: AgentState) -> AgentState:
    relations = state.get("detected_relations")

    if not relations:
        print("❌ No relationships detected")
    else:
        print("\n✅ DETECTED EXCEL RELATIONSHIPS\n")
        for file, rels in relations.items():
            print(f"📁 {file}")
            for r in rels:
                print(
                    f"  {r['from_sheet']}.{r['from_key']} → "
                    f"{r['to_sheet']}.{r['to_key']} "
                    f"(confidence={r['confidence']})"
                )
    return state
