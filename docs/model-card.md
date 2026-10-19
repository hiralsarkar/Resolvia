# Model card: root-cause classifier

| | |
|---|---|
| **Model** | Random Forest, 200 trees, `max_depth=None`, `min_samples_leaf=1` |
| **File** | `backend/models/ml_classifier/saved/root_cause_classifier.joblib` |
| **Trained by** | `backend/models/ml_classifier/train.py` (scikit-learn 1.9.0) |
| **Author** | Hiral Sarkar |

## What it's for

It predicts which of 20 root causes explains a post-trade break in Indian cash equities, given 15 features that measure how far the confirmation, position, cash and settlement records are from the booked trade. Its output is a recommendation inside the RCA agent. It never triggers an action on its own.

**Not for:** derivatives, FX or any other asset class; breaks with more than one cause; deciding whether an action should run. That last one is the Control Gate's job, and it doesn't use confidence at all.

## Data

6,000 synthetic trades and 3,000 synthetic breaks, 150 per root cause, split 80/20 by trade (2,393 train, 607 test). The data is generated, so there's no customer data and no personal data. The 50% break rate is set high for training, not to match reality.

## Performance (test set)

| Metric | Value |
|---|---:|
| Macro-F1 | 0.933 |
| Macro precision | 0.925 |
| Macro recall | 0.950 |
| Classes with F1 = 1.00 | 18 of 20 |
| CA mandatory not reflected | F1 0.66 |
| CA voluntary decision | F1 0.00 |

For comparison: a rules baseline scores 0.820, Logistic Regression 0.774 and XGBoost 0.932 (cross-validation). With the RCA agent reading the corporate action notice, the system scores 1.000.

## Known failure mode

The model can't tell a mandatory corporate action that wasn't applied from a voluntary one waiting for an election: their features are identical. It predicts "mandatory" for both, with about 50% confidence. This is designed into the data on purpose, and the system handles it in two ways: the RCA agent reads the MT564 notice, and every corporate action is sent to a person.

## Limitations

- Synthetic data with clean, single-cause faults. Real breaks are noisier, so real-world accuracy will be lower.
- Probabilities from a Random Forest are often exactly 0 or 1. I report them, but I don't use them to grant authority.
- No drift monitoring yet. In production I'd watch the confidence distribution and the rate of notice overrides.

## Responsible use

Use it to speed up investigation, never to skip review. Any action it leads to still goes through the Control Gate. See [Responsible AI and governance](08-responsible-ai.md).
