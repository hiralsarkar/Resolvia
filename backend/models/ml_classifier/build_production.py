"""
Builds the root-cause model the RCA agent actually runs.

train.py picks the algorithm and its settings on clean data. Clean data is
the easy case, so this script hardens that model in three steps:

1. Noise-augmented training. Besides the clean training breaks, the model
   sees three perturbed copies of them (price and cash jitter, plus a share of
   trades with a second fault; see data/perturb.py). Labels stay the cause the
   break feed reported.
2. Calibration. A random forest's vote shares are not probabilities, and most
   of them come out as exactly 0 or 1. Isotonic calibration, fitted with
   folds that keep every copy of a break together, turns them into
   probabilities a threshold can mean something against.
3. A threshold chosen by cost, not picked by hand. On a validation slice of
   the training trades (clean plus messy), every candidate threshold is
   replayed through the real routing rules: a review costs 1, a reopened fix
   5, a wrong fix that nobody saw 50. The cheapest threshold is kept.

Run from backend/ after train.py:  python models/ml_classifier/build_production.py
Writes saved/root_cause_production.joblib, which rca.py prefers when present.
"""

import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import LabelEncoder

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(HERE, "..", "..")
DATA_DIR = os.path.join(BACKEND, "..", "data")
for p in (DATA_DIR, BACKEND, os.path.join(BACKEND, "eval"), os.path.join(BACKEND, "agents")):
    sys.path.insert(0, p)

from features import build_features, load_frames, FEATURE_COLS  # noqa: E402
from perturb import perturb  # noqa: E402
from taxonomy import CA_ROOT_CAUSES  # noqa: E402
import sim  # noqa: E402

SAVED = os.path.join(HERE, "saved")
TUNED = {"n_estimators": 200, "max_depth": None, "min_samples_leaf": 1, "random_state": 42, "n_jobs": -1}

# (price/cash jitter, share of trades with a second fault, seed)
AUGMENT = [(0.001, 0.3, 101), (0.0025, 0.2, 102), (0.005, 0.1, 103)]
VALIDATION_STRESS = [(0.0, 0.0, 201), (0.005, 0.2, 202)]
THRESHOLDS = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]


def training_rows(frames, trade_ids):
    """Clean rows plus the augmented copies, for the given trades only."""
    parts = []
    clean = build_features(frames)
    parts.append(clean[clean.source_trade.isin(trade_ids)].assign(copy="clean"))
    for jitter, multi, seed in AUGMENT:
        f = build_features(perturb(frames, jitter=jitter, multi_cause=multi, split="TRAIN", seed=seed))
        parts.append(f[f.source_trade.isin(trade_ids)].assign(copy=f"aug{seed}"))
    return pd.concat(parts, ignore_index=True)


def fit(rows, le):
    X, y = rows[FEATURE_COLS], le.transform(rows["root_cause"])
    folds = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    splits = list(folds.split(X, y, groups=rows["break_id"]))
    model = CalibratedClassifierCV(RandomForestClassifier(**TUNED), method="isotonic", cv=splits)
    return model.fit(X, y)


def validation_rows(model, le, frames, trade_ids):
    out = []
    for jitter, multi, seed in VALIDATION_STRESS:
        pf = perturb(frames, jitter=jitter, multi_cause=multi, split="TRAIN", seed=seed)
        feats = build_features(pf).set_index("break_id")
        records = sim.records_by_trade(pf)
        brk = pf["breaks"]
        brk = brk[brk.source_record_id.isin(trade_ids)]
        proba = model.predict_proba(feats.loc[brk.break_id, FEATURE_COLS])
        for (_, b), p in zip(brk.iterrows(), proba):
            pred = le.classes_[p.argmax()]
            truth = {b["mismatch_type"], b.get("second_cause") or b["mismatch_type"]}
            out.append({
                "pred": pred, "conf": float(p.max()), "correct": pred in truth,
                "is_ca": isinstance(b["corporate_action_type"], str) and b["corporate_action_type"] != "",
                "outcome_if_run": sim.outcome(pred, sim.feed_of(b.to_dict()), records[b["source_record_id"]]),
            })
    return out


def main():
    frames = load_frames()
    le = LabelEncoder().fit(sorted(frames["breaks"]["mismatch_type"].unique()))
    train_trades = sorted(frames["trades"].query("split == 'TRAIN'").trade_id)

    rng = np.random.default_rng(7)
    val_trades = set(rng.choice(train_trades, size=len(train_trades) // 5, replace=False))
    fit_trades = [t for t in train_trades if t not in val_trades]

    print("choosing the threshold on a validation slice of the training trades...")
    model = fit(training_rows(frames, set(fit_trades)), le)
    rows = validation_rows(model, le, frames, val_trades)
    table = [sim.routing_cost(rows, t) for t in THRESHOLDS]
    best = min(table, key=lambda r: (r["cost"], r["reviews"]))
    for r in table:
        mark = "  <- chosen" if r is best else ""
        print(f"  t={r['threshold']:.2f} reviews={r['reviews']:4d} reopens={r['reopens']:3d} "
              f"silent={r['silent_errors']:3d} cost={r['cost']:5d}{mark}")

    print("fitting the final model on all training trades...")
    final = fit(training_rows(frames, set(train_trades)), le)
    bundle = {"model": final, "label_encoder": le, "features": FEATURE_COLS,
              "threshold": best["threshold"], "calibrated": "isotonic",
              "augmentation": AUGMENT, "params": TUNED}
    os.makedirs(SAVED, exist_ok=True)
    joblib.dump(bundle, os.path.join(SAVED, "root_cause_production.joblib"), compress=3)
    with open(os.path.join(SAVED, "production_meta.json"), "w") as f:
        json.dump({"threshold": best["threshold"], "threshold_table": table,
                   "costs": {"review": sim.COST_REVIEW, "reopen": sim.COST_REOPEN,
                             "silent_error": sim.COST_SILENT_ERROR},
                   "augmentation": AUGMENT, "validation_breaks": len(rows)}, f, indent=2)
    print(f"saved root_cause_production.joblib with threshold {best['threshold']}")


if __name__ == "__main__":
    main()
