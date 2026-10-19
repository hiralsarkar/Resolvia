# 6. Results

![Model comparison](images/results.svg)

| | Root-cause macro-F1 | Source |
|---|---:|---|
| Logistic Regression (5-fold CV) | 0.774 | `backend/models/ml_classifier/train.py` |
| Rules baseline (test) | 0.820 | `backend/eval/baseline_comparison.py` |
| XGBoost (5-fold CV) | 0.932 | `train.py` |
| Random Forest, tuned (test) | 0.933 | `train.py` |
| RCA agent: model plus the notice (test) | 1.000 | `backend/eval/pipeline_eval.py` |

The rules baseline gets every mechanical cause and none of the corporate-action ones. The model gets all but the mandatory and voluntary pair. Reading the notice gets the rest.

## The whole system on the test set

![Outcomes on the test set](images/outcomes.svg)

`pipeline_eval.py` runs every test break through the Orchestrator, approves anything waiting on a person, and counts the outcomes.

| Measure | Result |
|---|---:|
| Test breaks | 607 |
| Needed a person before anything ran | 466 (77%) |
| Ran straight through on policy | 141 (23%) |
| Closed after re-checking the records | 572 |
| On hold for a client election | 35 |
| Reopened | 0 |
| Unauthorised executions | 0 |

## Other numbers

| | |
|---|---:|
| Family, Triage model and derived from root cause | 1.000 |
| OCR key-token accuracy on the 30 scans (`backend/ocr/verify_ocr.py`) | about 99% |
| Manual baseline: evidence sources an analyst opens per break | 4.89 |
| Precedent cases (`backend/knowledge/resolved_cases.json`) | 400: 380 closed, 20 on hold |
| Root causes run end to end through the Orchestrator | 20 of 20 |

## Under stress

The numbers above are on clean data. With noise on prices and cash, a second fault on some trades, and damaged or missing notices, the RCA agent still scores 0.973 and no wrong fix runs unnoticed. That's in [stress tests and modelling depth](09-robustness.md).

## How I read these numbers

The data is synthetic and clean, so the near-perfect scores show that the features and the pipeline work, not that real breaks are this easy. The finding I'd expect to carry over is the shape of it: rules and a structured model both stall on the case that needs a document and a judgment, and that's the case I built the system around.

Next: [limits and next steps](07-limits-and-next-steps.md)
