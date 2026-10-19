# Model card: root-cause classifier

| | |
|---|---|
| **Model** | Random Forest (200 trees, `max_depth=None`, `min_samples_leaf=1`), trained on clean plus noise-augmented data, isotonic calibration |
| **File** | `backend/models/ml_classifier/saved/root_cause_production.joblib` |
| **Trained by** | `train.py` picks the algorithm and settings; `build_production.py` adds augmentation, calibration and the threshold (scikit-learn 1.9.1) |
| **Review threshold** | 0.80 calibrated confidence, chosen by cost on a validation slice of the training trades |
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

## Under stress

| Scenario | Clean-trained model | This model |
|---|---:|---:|
| 1% noise on prices and cash | 0.820 | 0.866 |
| Noise, two-fault trades, damaged and missing notices together | 0.904 | 0.937 |
| Calibration error on messy data (ECE) | 0.097 | 0.024 |

Full results are in [`analysis/robustness.md`](analysis/robustness.md).

## Known failure mode

The model can't tell a mandatory corporate action that wasn't applied from a voluntary one waiting for an election: their features are identical. It predicts "mandatory" for both. This is designed into the data on purpose, and the system handles it in two ways: the RCA agent reads the MT564 notice, and every corporate action is sent to a person.

## Limitations

- Synthetic data. Training includes noisy and two-fault copies, but real breaks are messy in ways I haven't simulated, so real-world accuracy will be lower.
- Calibration was fitted on synthetic noise. Real data may be noisy in other ways, so the threshold should be re-chosen on real breaks.
- Confidence only decides whether a person reviews the diagnosis. It never grants authority to act.

## Responsible use

Use it to speed up investigation, never to skip review. Any action it leads to still goes through the Control Gate. See [Responsible AI and governance](08-responsible-ai.md).
