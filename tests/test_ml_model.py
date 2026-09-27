import json

import numpy as np
import pandas as pd
import pytest

from src.risk_scoring.ml_model import RiskClassifier

SPEC = {
    "type": "logreg",
    "classes": ["Low", "Medium", "High"],
    "features": ["n_proximity", "n_count"],
    "mean": [0.5, 0.5],
    "scale": [0.5, 0.5],
    # Higher proximity pushes toward High, lower toward Low.
    "coef": [[-4.0, 0.0], [0.0, 0.0], [4.0, 0.0]],
    "intercept": [0.0, 0.5, 0.0],
}


def test_predict_uses_standardised_linear_softmax(tmp_path):
    p = tmp_path / "model.json"
    p.write_text(json.dumps(SPEC))
    clf = RiskClassifier.load(p)
    df = pd.DataFrame({"n_proximity": [0.0, 0.5, 1.0], "n_count": [0.2, 0.2, 0.2]})

    proba = clf.predict_proba(df)
    assert proba.shape == (3, 3) and np.allclose(proba.sum(axis=1), 1)
    assert clf.predict(df) == ["Low", "Medium", "High"]

    # Row 0 by hand: x = (0 - 0.5) / 0.5 = -1 -> logits [4, 0.5, -4]
    z = np.array([4.0, 0.5, -4.0])
    assert proba[0] == pytest.approx(np.exp(z) / np.exp(z).sum())


def test_missing_features_raise():
    with pytest.raises(KeyError, match="n_count"):
        RiskClassifier(SPEC).predict(pd.DataFrame({"n_proximity": [0.5]}))


def test_unknown_type_rejected():
    with pytest.raises(ValueError):
        RiskClassifier({**SPEC, "type": "forest"})
