import pandas as pd
from deterministic_agent import run_neuro_symbolic_agent




print("\n========== ORIGINAL DATA ==========")
print(df.head())
print("\nShape:", df.shape)


# ---------------------------------
#  Run Deterministic Agent
# ---------------------------------
cleaned_df, decisions = run_neuro_symbolic_agent(
    df=df,
    rules_path="rules.yaml"
)


# ---------------------------------
#  Show Decisions
# ---------------------------------
print("\n========== RULE DECISIONS ==========")
for d in decisions:
    print(d)


# ---------------------------------
#  Show Cleaned Data
# ---------------------------------
print("\n========== CLEANED DATA ==========")
print(cleaned_df.head())
print("\nNew Shape:", cleaned_df.shape)


# ---------------------------------
# Save Result (Optional)
# ---------------------------------
cleaned_df.to_csv("cleaned_output.csv", index=False)
print("\n✔ Cleaned dataset saved as cleaned_output.csv")