"""
Trains the family classifier that Triage uses for routing.

Family (POSITION, CASH, SETTLEMENT, TRADE) is easy to separate: tree models
get it right every time. That would be a weak target for the main model
comparison, but it's exactly what a routing step should be, cheap and nearly
certain. The harder root-cause model is trained in models/ml_classifier.
"""

import os
import sys
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data")
sys.path.insert(0, DATA_DIR)
from features import build_features, FEATURE_COLS  # noqa: E402

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
