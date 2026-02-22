from neural_signals import NeuralSignalGenerator
from rule_engine import RuleEngine

def run_neuro_symbolic(df):

    # Step 1: Neural signals
    neural = NeuralSignalGenerator()
    signals = neural.generate_signals(df)

    # Step 2: Deterministic rule execution
    engine = RuleEngine("rules.yaml")
    df = engine.apply(df, signals)

    return df, signals, engine.audit_log

