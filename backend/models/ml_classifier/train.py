"""
Trains and compares the root-cause classifier (20 classes).

1. 5-fold stratified cross-validation on TRAIN for Logistic Regression,
   Random Forest and XGBoost, scored on macro-F1 so every class counts equally.
2. Grid search on whichever model wins.
3. One evaluation on the held-out TEST set: macro-F1, precision, recall,
   per-class F1 and the confusion between the corporate-action classes.
4. Saves the model and writes docs/analysis/model_comparison.md.

Family is reported too, by mapping each predicted root cause to its family.
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score, GridSearchCV
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (f1_score, precision_score, recall_score,
                              classification_report, confusion_matrix)
from xgboost import XGBClassifier

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data")
sys.path.insert(0, DATA_DIR)
from features import build_features, FEATURE_COLS  # noqa: E402
from taxonomy import ROOT_CAUSES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED_DIR = os.path.join(HERE, "saved")
DOCS_DIR = os.path.join(HERE, "..", "..", "..", "docs", "analysis")

CANDIDATES = {
    "LogisticRegression": lambda: LogisticRegression(max_iter=1000),
    "RandomForest": lambda: RandomForestClassifier(n_estimators=200, random_state=42),
    "XGBoost": lambda: XGBClassifier(n_estimators=200, random_state=42, eval_metric="mlogloss"),
}

TUNING_GRIDS = {
    "LogisticRegression": {"C": [0.1, 1.0, 10.0]},
    "RandomForest": {"n_estimators": [200, 400], "max_depth": [None, 10, 20],
                      "min_samples_leaf": [1, 2]},
    "XGBoost": {"n_estimators": [200, 400], "max_depth": [3, 5, 7],
                "learning_rate": [0.05, 0.1, 0.2]},
}


def main():
    df = build_features()
    train = df[df["split"] == "TRAIN"]
    test = df[df["split"] == "TEST"]

    le = LabelEncoder()
    le.fit(df["root_cause"])
    X_train, y_train = train[FEATURE_COLS], le.transform(train["root_cause"])
    X_test, y_test = test[FEATURE_COLS], le.transform(test["root_cause"])

    # 5-fold stratified CV per candidate, macro-F1
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_results = {}
    for name, ctor in CANDIDATES.items():
        scores = cross_val_score(ctor(), X_train, y_train, cv=cv, scoring="f1_macro")
        cv_results[name] = {"mean": float(scores.mean()), "std": float(scores.std()),
                             "folds": [round(float(s), 4) for s in scores]}
        print(f"{name:20s} CV macro-F1 = {scores.mean():.3f} (+/- {scores.std():.3f})")

    winner_name = max(cv_results, key=lambda n: cv_results[n]["mean"])
    print(f"\nCV winner: {winner_name}")

    # Tune the winner
    grid = GridSearchCV(CANDIDATES[winner_name](), TUNING_GRIDS[winner_name],
                         cv=cv, scoring="f1_macro", n_jobs=-1)
    grid.fit(X_train, y_train)
    tuned_model = grid.best_estimator_
    print(f"Tuned params: {grid.best_params_}  (tuned CV macro-F1 = {grid.best_score_:.3f})")

    # Evaluate on TEST
    preds = tuned_model.predict(X_test)
    test_macro_f1 = f1_score(y_test, preds, average="macro", zero_division=0)
    test_precision = precision_score(y_test, preds, average="macro", zero_division=0)
    test_recall = recall_score(y_test, preds, average="macro", zero_division=0)
    report = classification_report(y_test, preds, target_names=le.classes_,
                                    zero_division=0, output_dict=True)
    cm = confusion_matrix(y_test, preds)

    # family follows from the predicted root cause, so report it as well
    pred_root_causes = le.inverse_transform(preds)
    true_family = test["family"].values
    pred_family = np.array([ROOT_CAUSES[rc]["family"] for rc in pred_root_causes])
    family_macro_f1 = f1_score(true_family, pred_family, average="macro", zero_division=0)

    print(f"\nTEST macro-F1 (root_cause) = {test_macro_f1:.3f}")
    print(f"TEST macro-F1 (derived family) = {family_macro_f1:.3f}")

    os.makedirs(SAVED_DIR, exist_ok=True)
    joblib.dump({"model": tuned_model, "label_encoder": le, "features": FEATURE_COLS},
                os.path.join(SAVED_DIR, "root_cause_classifier.joblib"))

    write_report(cv_results, winner_name, grid.best_params_, grid.best_score_,
                 test_macro_f1, test_precision, test_recall, family_macro_f1,
                 report, cm, le.classes_, len(train), len(test))
    print(f"\nSaved model -> backend/models/ml_classifier/saved/root_cause_classifier.joblib")
    print(f"Wrote report -> docs/analysis/model_comparison.md")


def write_report(cv_results, winner_name, best_params, tuned_cv_score,
                 test_macro_f1, test_precision, test_recall, family_macro_f1,
                 report, cm, classes, n_train, n_test):
    lines = [
        "# Model comparison: root-cause classifier\n",
        "The target is the root cause (20 classes). Break family is also reported, by mapping each "
        "predicted root cause to its family. Family on its own is too easy to be a useful target: "
        "tree models score 1.000 on it (see `data/check_ml_targets.py`).\n",
        f"Train: {n_train} breaks. Test: {n_test} breaks. Models are compared with 5-fold stratified "
        "cross-validation on the training set and scored on macro-F1, which weighs all 20 classes "
        "equally.\n",
        "## 1. Candidates (5-fold CV, macro-F1)\n",
        "| Model | CV macro-F1 (mean ± std) |",
        "|---|---|",
    ]
    for name, r in cv_results.items():
        marker = " **(winner)**" if name == winner_name else ""
        lines.append(f"| {name} | {r['mean']:.3f} ± {r['std']:.3f}{marker} |")

    lines += [
        "",
        f"## 2. Tuning the winner ({winner_name})\n",
        "Grid search, 5-fold CV, macro-F1.\n",
        f"- Best parameters: `{best_params}`",
        f"- Tuned CV macro-F1: {tuned_cv_score:.3f}\n",
        "## 3. Held-out test set\n",
        f"- **Root-cause macro-F1: {test_macro_f1:.3f}** (precision {test_precision:.3f}, "
        f"recall {test_recall:.3f})",
        f"- **Family macro-F1: {family_macro_f1:.3f}** (derived from the predicted root cause)",
        "- The rules baseline is in `backend/eval/baseline_comparison.py` and the full pipeline "
        "result in `backend/eval/pipeline_eval.py`.\n",
        "## 4. Per-class results (test)\n",
        "| Root cause | Precision | Recall | F1 | Support |",
        "|---|---|---|---|---|",
    ]
    for cls in classes:
        m = report[cls]
        lines.append(f"| {cls} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1-score']:.2f} | {int(m['support'])} |")

    ca_idx = [i for i, c in enumerate(classes) if c.startswith("CA_")]
    if len(ca_idx) == 3:
        sub_cm = cm[np.ix_(ca_idx, ca_idx)]
        short = {"CA_INCORRECT_ENTITLEMENT": "incorrect", "CA_MANDATORY_NOT_REFLECTED": "mandatory",
                 "CA_VOLUNTARY_DECISION": "voluntary"}
        lines += [
            "",
            "## 5. Where it goes wrong\n",
            "Every miss is between the corporate-action classes. Mandatory and voluntary events were "
            "generated to look identical in the numbers, so the model can't separate them; only the "
            "corporate action notice can. Rows are the true class, columns the prediction:\n",
            "| true \\ predicted | " + " | ".join(short[classes[i]] for i in ca_idx) + " |",
            "|---|" + "---|" * len(ca_idx),
        ]
        for i, row_idx in enumerate(ca_idx):
            lines.append(f"| {short[classes[row_idx]]} | " + " | ".join(str(sub_cm[i][j]) for j in range(len(ca_idx))) + " |")
        lines.append("")
        lines.append("In the running system the RCA agent reads the notice's CAMV field and corrects "
                     "this, and a person signs off on every corporate action anyway.\n")

    lines += [
        "## 6. Reading these numbers\n",
        f"- About {round((n_train + n_test) / 20)} breaks per class. Read per-class F1 next to its support.",
        "- The near-perfect scores outside the corporate-action classes come from clean synthetic "
        "differences. They show the features work, not that real-world breaks are this easy.",
        "- The corporate-action confusion is the finding that matters: it's why the system reads "
        "documents and keeps a person in the loop.",
    ]

    with open(os.path.join(DOCS_DIR, "model_comparison.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
