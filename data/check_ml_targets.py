"""
Which target should the classifier learn: break family or root cause?

Fits the same three models (Logistic Regression, Random Forest, XGBoost) on
the same features against both targets and prints macro-F1 for each. This is
a quick check with a single train/test split, no tuning. It's what decided
that root cause, not family, is the target worth modelling.

Only broken trades are used; a clean trade has no root cause.
"""

from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from xgboost import XGBClassifier

from features import build_features, FEATURE_COLS

MODELS = {
    "LogisticRegression": lambda: LogisticRegression(max_iter=1000),
    "RandomForest": lambda: RandomForestClassifier(n_estimators=200, random_state=42),
    "XGBoost": lambda: XGBClassifier(n_estimators=200, random_state=42, eval_metric="mlogloss"),
}


def fit_and_report(df, target_col, label):
    X = df[FEATURE_COLS]
    y_raw = df[target_col]
    train_mask = df["split"] == "TRAIN"

    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    X_train, X_test = X[train_mask], X[~train_mask]
    y_train, y_test = y[train_mask.values], y[~train_mask.values]

    print(f"\n=== Target: {label} ({df[target_col].nunique()} classes) "
          f"| train={len(X_train)} test={len(X_test)} ===")
    for name, ctor in MODELS.items():
        model = ctor()
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        macro_f1 = f1_score(y_test, preds, average="macro", zero_division=0)
        print(f"  {name:20s} macro-F1 = {macro_f1:.3f}")


if __name__ == "__main__":
    df = build_features()
    print(f"Built features for {len(df)} breaking trades.")
    fit_and_report(df, "family", "4-class break family (POSITION/CASH/SETTLEMENT/TRADE)")
    fit_and_report(df, "root_cause", "20-class root cause")
