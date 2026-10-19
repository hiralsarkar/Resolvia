# Robustness report

Written by `backend/eval/robustness.py`. All numbers are on the 607 held-out test breaks. `clean` is the tuned random forest trained on clean data; `production` is the noise-trained, calibrated model the RCA agent uses. Agent F1 includes reading the corporate action notice. Reviewed, reopened and silent errors replay the routing rules with the production threshold (0.8).

## Price and cash jitter

| jitter | model F1 clean / prod | agent F1 clean / prod | reviewed | reopened | silent errors |
|---|---|---|---|---|---|
| 0.0 | 0.933 / 0.933 | 1.0 / 1.0 | 466 | 0 | 0 |
| 0.001 | 0.931 / 0.945 | 0.998 / 1.0 | 470 | 0 | 0 |
| 0.0025 | 0.922 / 0.941 | 0.99 / 0.995 | 472 | 0 | 0 |
| 0.005 | 0.877 / 0.934 | 0.943 / 0.984 | 473 | 0 | 0 |
| 0.01 | 0.82 / 0.866 | 0.877 / 0.924 | 485 | 0 | 0 |

## Second fault on the same trade

| share | model F1 clean / prod | agent F1 clean / prod | reviewed | reopened | silent errors |
|---|---|---|---|---|---|
| 0.0 | 0.933 / 0.933 | 1.0 / 1.0 | 466 | 0 | 0 |
| 0.1 | 0.939 / 0.939 | 1.0 / 1.0 | 478 | 0 | 0 |
| 0.2 | 0.963 / 0.961 | 1.0 / 0.998 | 483 | 4 | 0 |
| 0.3 | 0.961 / 0.959 | 1.0 / 0.998 | 496 | 4 | 0 |
| 0.4 | 0.967 / 0.964 | 1.0 / 0.997 | 498 | 14 | 0 |

## Everything at once

Jitter 0.005, a second fault on 20% of trades, notices scanned at a 5% character error rate and 25% of them missing.

| model | model F1 | agent F1 | reviewed | reopened | silent errors |
|---|---|---|---|---|---|
| clean | 0.904 | 0.939 | 492 | 2 | 0 |
| production | 0.937 | 0.973 | 496 | 4 | 0 |

## Corporate action notices (99 test corporate actions)

Accuracy on the corporate-action breaks only, as the notice gets harder to read.

| character error rate | exact parser | hardened parser |
|---|---|---|
| 0.0 | 1.0 | 1.0 |
| 0.05 | 0.879 | 1.0 |
| 0.1 | 0.758 | 1.0 |
| 0.2 | 0.687 | 1.0 |
| 0.3 | 0.646 | 0.96 |

| share of notices missing | accuracy |
|---|---|
| 0.0 | 1.0 |
| 0.25 | 0.939 |
| 0.5 | 0.788 |
| 1.0 | 0.646 |

## Label noise in training

| labels flipped | test macro-F1 |
|---|---|
| 0.0 | 0.933 |
| 0.05 | 0.931 |
| 0.1 | 0.93 |
| 0.2 | 0.919 |

## Calibration

Expected calibration error (lower is better), Brier score, and the share of predictions with confidence exactly 0 or 1.

| data | model | ECE | Brier | share at 0 or 1 |
|---|---|---|---|---|
| clean | clean | 0.002 | 0.057 | 0.855 |
| clean | production | 0.015 | 0.057 | 0.0 |
| messy | clean | 0.097 | 0.301 | 0.539 |
| messy | production | 0.024 | 0.219 | 0.0 |
