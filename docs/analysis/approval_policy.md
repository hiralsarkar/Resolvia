# Approval policy and reviewer error

Written by `backend/eval/approval_policy.py` on the 607 test breaks. Messy = price and cash jitter 0.005 plus a second fault on 20% of trades; very messy = jitter 0.01 and a second fault on 40%. Reviewer figures are expected counts. Risk-based rules only auto-run controlled actions that are not P0, not corporate actions, and have calibrated confidence of at least 0.95.

## Policies, clean data

| policy | reviewed by a person | controlled fixes run without review | value of those (₹ crore) | reopened | silent errors |
|---|---|---|---|---|---|
| strict (live) | 76.8% | 0 | 0.0 | 0 | 0 |
| auto under 1 lakh | 74.1% | 16 | 0.1 | 0 | 0 |
| auto under 5 lakh | 62.8% | 85 | 2.03 | 0 | 0 |
| auto under 10 lakh | 54.9% | 133 | 5.73 | 0 | 0 |

## Reviewers who miss mistakes, clean data (strict policy)

| reviewer miss rate | wrong diagnoses reviewed | caught by the reviewer | caught by validation | slipped through |
|---|---|---|---|---|
| 0.0 | 0 | 0.0 | 0.0 | 0.0 |
| 0.05 | 0 | 0.0 | 0.0 | 0.0 |
| 0.1 | 0 | 0.0 | 0.0 | 0.0 |
| 0.2 | 0 | 0.0 | 0.0 | 0.0 |

## Policies, messy data

| policy | reviewed by a person | controlled fixes run without review | value of those (₹ crore) | reopened | silent errors |
|---|---|---|---|---|---|
| strict (live) | 81.1% | 0 | 0.0 | 1 | 0 |
| auto under 1 lakh | 79.2% | 11 | 0.06 | 2 | 0 |
| auto under 5 lakh | 71.8% | 56 | 1.39 | 12 | 0 |
| auto under 10 lakh | 67.7% | 81 | 3.27 | 17 | 0 |

## Reviewers who miss mistakes, messy data (strict policy)

| reviewer miss rate | wrong diagnoses reviewed | caught by the reviewer | caught by validation | slipped through |
|---|---|---|---|---|
| 0.0 | 9 | 9.0 | 0.0 | 0.0 |
| 0.05 | 9 | 8.5 | 0.2 | 0.2 |
| 0.1 | 9 | 8.1 | 0.5 | 0.4 |
| 0.2 | 9 | 7.2 | 1.0 | 0.8 |

## Policies, very messy data

| policy | reviewed by a person | controlled fixes run without review | value of those (₹ crore) | reopened | silent errors |
|---|---|---|---|---|---|
| strict (live) | 85.0% | 0 | 0.0 | 7 | 0 |
| auto under 1 lakh | 84.3% | 4 | 0.02 | 10 | 0 |
| auto under 5 lakh | 80.7% | 26 | 0.61 | 14 | 0 |
| auto under 10 lakh | 78.6% | 39 | 1.58 | 18 | 0 |

## Reviewers who miss mistakes, very messy data (strict policy)

| reviewer miss rate | wrong diagnoses reviewed | caught by the reviewer | caught by validation | slipped through |
|---|---|---|---|---|
| 0.0 | 35 | 35.0 | 0.0 | 0.0 |
| 0.05 | 35 | 33.2 | 1.5 | 0.3 |
| 0.1 | 35 | 31.5 | 2.9 | 0.6 |
| 0.2 | 35 | 28.0 | 5.8 | 1.2 |
