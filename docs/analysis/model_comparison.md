# Model comparison: root-cause classifier

The target is the root cause (20 classes). Break family is also reported, by mapping each predicted root cause to its family. Family on its own is too easy to be a useful target: tree models score 1.000 on it (see `data/check_ml_targets.py`).

Train: 2393 breaks. Test: 607 breaks. Models are compared with 5-fold stratified cross-validation on the training set and scored on macro-F1, which weighs all 20 classes equally.

## 1. Candidates (5-fold CV, macro-F1)

| Model | CV macro-F1 (mean ± std) |
|---|---|
| LogisticRegression | 0.774 ± 0.012 |
| RandomForest | 0.933 ± 0.000 **(winner)** |
| XGBoost | 0.932 ± 0.003 |

## 2. Tuning the winner (RandomForest)

Grid search, 5-fold CV, macro-F1.

- Best parameters: `{'max_depth': None, 'min_samples_leaf': 1, 'n_estimators': 200}`
- Tuned CV macro-F1: 0.933

## 3. Held-out test set

- **Root-cause macro-F1: 0.933** (precision 0.925, recall 0.950)
- **Family macro-F1: 1.000** (derived from the predicted root cause)
- The rules baseline is in `backend/eval/baseline_comparison.py` and the full pipeline result in `backend/eval/pipeline_eval.py`.

## 4. Per-class results (test)

| Root cause | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| CASH_DUPLICATE_ENTRY | 1.00 | 1.00 | 1.00 | 35 |
| CASH_FX_INPUT_DIFFERENCE | 1.00 | 1.00 | 1.00 | 25 |
| CASH_MISSING_ENTRY | 1.00 | 1.00 | 1.00 | 28 |
| CASH_WRONG_AMOUNT | 1.00 | 1.00 | 1.00 | 31 |
| CA_INCORRECT_ENTITLEMENT | 1.00 | 1.00 | 1.00 | 30 |
| CA_MANDATORY_NOT_REFLECTED | 0.49 | 1.00 | 0.66 | 34 |
| CA_VOLUNTARY_DECISION | 0.00 | 0.00 | 0.00 | 35 |
| CONF_DISAGREEMENT | 1.00 | 1.00 | 1.00 | 28 |
| CONF_MISSING | 1.00 | 1.00 | 1.00 | 25 |
| POS_MISSING_BOOKING | 1.00 | 1.00 | 1.00 | 24 |
| POS_TIMING_DIFFERENCE | 1.00 | 1.00 | 1.00 | 26 |
| POS_WRONG_QUANTITY | 1.00 | 1.00 | 1.00 | 37 |
| SETL_INCORRECT_DATE | 1.00 | 1.00 | 1.00 | 30 |
| SETL_LATE_COUNTERPARTY | 1.00 | 1.00 | 1.00 | 32 |
| SETL_MISSING_INSTRUCTION | 1.00 | 1.00 | 1.00 | 29 |
| SETL_WRONG_SSI | 1.00 | 1.00 | 1.00 | 44 |
| TRADE_COUNTERPARTY_ID_MISMATCH | 1.00 | 1.00 | 1.00 | 26 |
| TRADE_DATE_MISMATCH | 1.00 | 1.00 | 1.00 | 28 |
| TRADE_PRICE_MISMATCH | 1.00 | 1.00 | 1.00 | 25 |
| TRADE_QUANTITY_MISMATCH | 1.00 | 1.00 | 1.00 | 35 |

## 5. Where it goes wrong

Every miss is between the corporate-action classes. Mandatory and voluntary events were generated to look identical in the numbers, so the model can't separate them; only the corporate action notice can. Rows are the true class, columns the prediction:

| true \ predicted | incorrect | mandatory | voluntary |
|---|---|---|---|
| incorrect | 30 | 0 | 0 |
| mandatory | 0 | 34 | 0 |
| voluntary | 0 | 35 | 0 |

In the running system the RCA agent reads the notice's CAMV field and corrects this, and a person signs off on every corporate action anyway.

## 6. Reading these numbers

- About 150 breaks per class. Read per-class F1 next to its support.
- The near-perfect scores outside the corporate-action classes come from clean synthetic differences. They show the features work, not that real-world breaks are this easy.
- The corporate-action confusion is the finding that matters: it's why the system reads documents and keeps a person in the loop.
