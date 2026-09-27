"""Explainable risk scoring and Low/Medium/High classification.

Fourth stage of the AviSense pipeline:
    ... -> Feature extraction -> Risk scoring -> Risk classification -> Dashboard

    risk_score = w_count*count + w_speed*speed + w_proximity*proximity
               + w_flock*flock_size + w_time*time_of_day

Each term is normalised to [0, 1] and weights sum to 1 (configs/risk.yaml).
Every output row keeps the weighted contribution of each term (c_*) and the
largest one (top_factor), so any alert can be explained.

Usage (from the project root):
    python -m src.risk_scoring.risk --features data/processed/frame_features.csv \
        --out data/processed/risk.csv --alerts-out data/processed/alerts.csv
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

FACTORS = ["count", "speed", "proximity", "flock_size", "time_of_day"]
LEVELS = ["Low", "Medium", "High"]
DEFAULT_CONFIG = "configs/risk.yaml"


@dataclass
class RiskConfig:
    weights: dict[str, float]
    normalise: dict[str, float]
    time_of_day: dict = field(default_factory=dict)
    levels: dict[str, float] = field(default_factory=lambda: {"medium": 0.3, "high": 0.6})
    smoothing_frames: int = 1
    alerts: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG) -> "RiskConfig":
        cfg = cls(**yaml.safe_load(Path(path).read_text()))
        missing = set(FACTORS) - set(cfg.weights)
        if missing:
            raise ValueError(f"Missing weights for: {sorted(missing)}")
        total = sum(cfg.weights[f] for f in FACTORS)
        if not np.isclose(total, 1.0):
            raise ValueError(f"Weights must sum to 1, got {total:.3f}")
        return cfg


def time_of_day_value(hour: float, cfg: RiskConfig) -> float:
    tod = cfg.time_of_day
    if hour is None or pd.isna(hour):
        return tod.get("unknown", 0.5)
    for w in tod.get("windows", []):
        if w["start"] <= hour < w["end"]:
            return w["value"]
    return tod.get("default", 0.0)


def normalise(ff: pd.DataFrame, cfg: RiskConfig) -> pd.DataFrame:
    """Map per-frame features to [0, 1] risk terms, one column per factor."""
    n = cfg.normalise
    has_birds = ff["count"] > 0
    hours = ff["hour"] if "hour" in ff else pd.Series(np.nan, index=ff.index)
    return pd.DataFrame({
        "count": (ff["count"] / n["count_cap"]).clip(0, 1),
        "speed": (ff["max_speed"] / n["speed_cap"]).clip(0, 1),
        # 1 inside a zone, falling linearly to 0 at proximity_range; 0 with no birds.
        "proximity": (1 - ff["min_dist_to_zone"] / n["proximity_range"]).clip(0, 1).fillna(0.0),
        "flock_size": (ff["flock_size"] / n["flock_cap"]).clip(0, 1),
        # Time of day raises risk only when birds are present.
        "time_of_day": hours.map(lambda h: time_of_day_value(h, cfg)).where(has_birds, 0.0),
    }, index=ff.index)


def classify(score: float, cfg: RiskConfig) -> str:
    if score >= cfg.levels["high"]:
        return "High"
    if score >= cfg.levels["medium"]:
        return "Medium"
    return "Low"


def score(ff: pd.DataFrame, cfg: RiskConfig) -> pd.DataFrame:
    """Add risk terms, weighted contributions, smoothed score, level and top factor."""
    terms = normalise(ff, cfg)
    out = ff.copy()
    for f in FACTORS:
        out[f"n_{f}"] = terms[f]
        out[f"c_{f}"] = terms[f] * cfg.weights[f]
    contrib = out[[f"c_{f}" for f in FACTORS]]
    out["risk_raw"] = contrib.sum(axis=1)
    out["risk_score"] = out["risk_raw"].rolling(max(1, cfg.smoothing_frames), min_periods=1).mean()
    out["risk_level"] = out["risk_score"].map(lambda s: classify(s, cfg))
    out["top_factor"] = np.where(out["risk_raw"] > 0,
                                 contrib.idxmax(axis=1).str.removeprefix("c_"), "")
    return out


def alert_episodes(risk: pd.DataFrame, cfg: RiskConfig) -> pd.DataFrame:
    """Group consecutive frames at or above the alert level into episodes."""
    a = cfg.alerts
    min_rank = LEVELS.index(a.get("min_level", "Medium"))
    rank = risk["risk_level"].map(LEVELS.index)
    hot = risk[rank >= min_rank]
    cols = ["start_s", "end_s", "duration_s", "start_frame", "end_frame",
            "peak_score", "peak_level", "top_factor", "max_count"]
    if hot.empty:
        return pd.DataFrame(columns=cols)

    # A new episode starts when the gap from the previous hot frame exceeds merge_gap_s.
    gap = hot["time_s"].diff().fillna(np.inf) > a.get("merge_gap_s", 0.0)
    gap.iloc[0] = True
    episodes = []
    for _, ep in hot.groupby(gap.cumsum()):
        peak = ep.loc[ep["risk_score"].idxmax()]
        episodes.append({
            "start_s": ep["time_s"].iloc[0],
            "end_s": ep["time_s"].iloc[-1],
            "duration_s": ep["time_s"].iloc[-1] - ep["time_s"].iloc[0],
            "start_frame": int(ep["frame_idx"].iloc[0]),
            "end_frame": int(ep["frame_idx"].iloc[-1]),
            "peak_score": float(peak["risk_score"]),
            "peak_level": peak["risk_level"],
            # The factor contributing most over the whole episode.
            "top_factor": ep[[f"c_{f}" for f in FACTORS]].sum().idxmax().removeprefix("c_"),
            "max_count": int(ep["count"].max()),
        })
    df = pd.DataFrame(episodes, columns=cols)
    return df[df["duration_s"] >= a.get("min_duration_s", 0.0)].reset_index(drop=True)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="AviSense: score risk from per-frame features.")
    p.add_argument("--features", required=True, help="Per-frame features CSV (src.risk_scoring.features).")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="Risk config YAML.")
    p.add_argument("--out", required=True, help="Output per-frame risk CSV.")
    p.add_argument("--alerts-out", default=None, help="Optional alert episodes CSV.")
    p.add_argument("--ml-model", default=None,
                   help="Optional classifier JSON from the Colab notebook; adds an ml_level column.")
    args = p.parse_args(argv)

    cfg = RiskConfig.load(args.config)
    risk = score(pd.read_csv(args.features), cfg)
    if args.ml_model:
        from src.risk_scoring.ml_model import RiskClassifier
        risk["ml_level"] = RiskClassifier.load(args.ml_model).predict(risk)
        agree = (risk["ml_level"] == risk["risk_level"]).mean()
        print(f"ML classifier agrees with the formula on {agree:.0%} of frames")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    risk.to_csv(args.out, index=False)
    print(f"Risk for {len(risk)} frames saved to {args.out}")
    print(risk["risk_level"].value_counts().reindex(LEVELS, fill_value=0).to_string())

    if args.alerts_out:
        eps = alert_episodes(risk, cfg)
        eps.to_csv(args.alerts_out, index=False)
        print(f"{len(eps)} alert episode(s) saved to {args.alerts_out}")


if __name__ == "__main__":
    main()
