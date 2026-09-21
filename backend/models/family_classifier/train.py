"""
train.py - the Triage Agent's family classifier.

This is the OTHER half of the family-vs-root_cause reconciliation: the official proposal's literal methodology
step 4 ("classify breaks into TRADE/SETTLEMENT/POSITION/CASH") maps
cleanly onto TRIAGE, not RCA. Family IS trivially separable (RF/XGBoost
hit 1.000 macro-F1 in Week 1's check_ml_targets.py) - and that's
appropriate here: a fast first-pass routing decision should be cheap
and near-certain, not deep. The hard, genuinely diagnostic
classification (root_cause) is correctly reserved for RCA, later in
the pipeline once real investigation has happened. Reporting the same
1.000 macro-F1 as a Triage result is not a flaw here the way it would
have been as the RCA target - it's the honest finding for what a
routing step should do.

No tuning/CV writeup needed here (that rigor already lives in
docs/model_comparison.md for the root_cause target) - this is a much
simpler fit, saved for the Triage Agent to load.
"""

import os
import sys
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data")
sys.path.insert(0, DATA_DIR)
from check_ml_targets import build_features, FEATURE_COLS  # noqa: E402

SAVED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved")


def main():
    df = build_features()
    train = df[df["split"] == "TRAIN"]

    le = LabelEncoder()
    le.fit(df["family"])
    X_train, y_train = train[FEATURE_COLS], le.transform(train["family"])

    model = RandomForestClassifier(n_estimators=200, random_state=42)
    model.fit(X_train, y_train)

    test = df[df["split"] == "TEST"]
    test_acc = model.score(test[FEATURE_COLS], le.transform(test["family"]))
    print(f"Family classifier TEST accuracy: {test_acc:.3f} (n={len(test)})")

    os.makedirs(SAVED_DIR, exist_ok=True)
    joblib.dump({"model": model, "label_encoder": le, "features": FEATURE_COLS},
                os.path.join(SAVED_DIR, "family_classifier.joblib"))
    print(f"Saved -> backend/models/family_classifier/saved/family_classifier.joblib")


if __name__ == "__main__":
    main()
