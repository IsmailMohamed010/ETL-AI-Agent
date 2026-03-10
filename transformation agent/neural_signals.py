import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

class SignalNetwork(nn.Module):
    def __init__(self, input_dim=4):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, 16)
        self.fc2 = nn.Linear(16, 8)
        self.out = nn.Linear(8, 1)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return torch.sigmoid(self.out(x))


class NeuralSignalGenerator:
    """
    Neural component:
    Produces signals only.
    Never decides rule execution.
    """

    def __init__(self):
        torch.manual_seed(42)  # deterministic weights
        self.model = SignalNetwork()
        self.model.eval()

    def generate_signals(self, df):
        signals = {}

        null_ratio = df.isna().mean().mean()
        row_count = len(df)
        col_count = len(df.columns)
        numeric_ratio = len(df.select_dtypes(include=np.number).columns) / max(1, col_count)

        features = torch.tensor(
            [null_ratio, row_count / 1e6, col_count / 100, numeric_ratio],
            dtype=torch.float32
        )

        with torch.no_grad():
            risk_score = self.model(features).item()

        signals["global_risk_score"] = round(risk_score, 3)
        signals["avg_null_ratio"] = round(null_ratio, 3)

        return signals
