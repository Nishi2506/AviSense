"""Run the ML risk classifier trained in notebooks/risk_classifier_colab.ipynb.

The notebook exports a multinomial logistic regression as plain JSON
(standardisation + coefficients), so prediction needs only NumPy here:

    {"type": "logreg", "classes": ["Low", "Medium", "High"], "features": [...],
     "mean": [...], "scale": [...], "coef": [[...], ...], "intercept": [...]}
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


class RiskClassifier:
    def __init__(self, spec: dict) -> None:
        if spec.get("type") != "logreg":
            raise ValueError(f"Unsupported model type: {spec.get('type')!r}")
        self.classes: list[str] = spec["classes"]
        self.features: list[str] = spec["features"]
        self.mean = np.asarray(spec["mean"], dtype=float)
        self.scale = np.asarray(spec["scale"], dtype=float)
        self.coef = np.asarray(spec["coef"], dtype=float)          # (n_classes, n_features)
        self.intercept = np.asarray(spec["intercept"], dtype=float)  # (n_classes,)

    @classmethod
    def load(cls, path: str | Path) -> "RiskClassifier":
        return cls(json.loads(Path(path).read_text()))

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        missing = [f for f in self.features if f not in df]
        if missing:
            raise KeyError(f"Missing feature columns: {missing}")
        x = (df[self.features].to_numpy(dtype=float) - self.mean) / self.scale
        logits = x @ self.coef.T + self.intercept
        logits -= logits.max(axis=1, keepdims=True)  # numerically stable softmax
        p = np.exp(logits)
        return p / p.sum(axis=1, keepdims=True)

    def predict(self, df: pd.DataFrame) -> list[str]:
        return [self.classes[i] for i in self.predict_proba(df).argmax(axis=1)]
