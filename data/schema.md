# Data dictionary

Everything in this folder is synthetic. There is no public dataset of real trade breaks, because trade and reconciliation data is confidential at every bank, custodian and broker. So, the same way PaySim does for fraud, I simulated clean operations, injected known faults and kept the answer.

`generate_trade_breaks.py` plays the bank's existing reconciliation engine. Resolvia doesn't do matching; it starts from the break feed this script produces.

All five tables carry a `split` column (`TRAIN` or `TEST`, 80/20 by trade, fixed by `random.seed(42)`).

## trades.csv

One row per trade. The booked view, plus the counterparty's confirmed view of the same trade.

| Column | Meaning |
|---|---|
| trade_id | Primary key |
| trade_date, settlement_date | T and T+1 (Indian market) |
| security, isin, ticker | Instrument |
| quantity, price, trade_value | Economics as booked |
| counterparty, portfolio | Who we traded with, and for which book |
| booking_status | Always BOOKED here |
| side | BUY or SELL |
| confirmed_price, confirmed_quantity, confirmed_trade_date, confirmed_counterparty | What the counterparty confirmed. Matches the booking unless a TRADE-family fault was injected. This is what makes trade breaks visible without reading the label. |
| confirmation_status | RECEIVED, or MISSING for `CONF_MISSING` |

## positions.csv

One row per trade. What the custodian says we hold.

| Column | Meaning |
|---|---|
| position_id | Primary key |
| trade_id | Links to trades |
| security, portfolio | Copied for convenience |
| expected_quantity | The booked quantity |
| actual_quantity | What the custodian shows. Differs for POSITION breaks, including the three corporate-action causes |
| as_of_date | Differs for `POS_TIMING_DIFFERENCE` |
| source | CUSTODIAN, or MISSING for `POS_MISSING_BOOKING` |

## cash_transactions.csv

Zero, one or two rows per trade: one for a clean trade, none for `CASH_MISSING_ENTRY`, two for `CASH_DUPLICATE_ENTRY`.

| Column | Meaning |
|---|---|
| cash_id | Primary key |
| trade_id | Links to trades |
| account, currency | Where the cash posted and in what currency (wrong for `CASH_FX_INPUT_DIFFERENCE`) |
| amount | What actually posted |
| expected_amount | The trade value |
| value_date, transaction_type, status | Operational details |

## settlements.csv

One row per trade. How the trade actually settled.

| Column | Meaning |
|---|---|
| settlement_id | Primary key |
| trade_id | Links to trades |
| settlement_date | Two to five days late for `SETL_LATE_COUNTERPARTY` (status PENDING); one day off for `SETL_INCORRECT_DATE` (status stays SETTLED) |
| settlement_status | SETTLED, PENDING or FAILED |
| instruction_status | INSTRUCTED, MISSING or INCORRECT |
| custodian | The counterparty |
| quantity, amount | What settled |
| ssi_code | The settlement instruction actually used. Wrong for `SETL_WRONG_SSI`, the failed-payment case |

## breaks.csv

One row per broken trade. That's 50% of trades, far more than the 1 to 5% a real desk sees, so that every root cause gets 150 examples.

| Column | Meaning |
|---|---|
| break_id | Primary key |
| reconciliation_id, business_date | Batch details |
| break_type | Family: POSITION, CASH, SETTLEMENT or TRADE. Tagged by the reconciliation engine and used for routing |
| mismatch_type | **The root cause.** Ground truth for training and evaluation only; the running system never reads it |
| root_cause | Plain-English description of the root cause. Also ground truth |
| source_system, comparison_system | The two systems that disagree |
| source_record_id, comparison_record_id | Both the trade_id here |
| source_value, target_value | Expected and observed values |
| breaking_fields | The field (or fields) that disagree |
| severity | P0 (settlement or critical risk), P1, P2 |
| status, age | OPEN and 0 for every row; the lifecycle starts once Resolvia opens a case |
| counterparty, client | From the trade |
| corporate_action_type | MANDATORY or VOLUNTARY for the three corporate-action causes, otherwise blank |
| needs_evidence_bundle | True if the break has a document: every corporate-action, settlement and trade break, plus about a quarter of the rest (2,212 of 3,000) |

## Documents

`broker_confirms/` holds one text document per evidence break and `broker_confirms_mapping.csv` links each to its break. Corporate actions get a SWIFT MT564-style notice, settlement breaks an MT54x-style message, trade breaks an NSE-style contract note, and position and cash breaks ordinary ops emails and chat messages. `scanned_images/` has 30 of them rendered as noisy scans for OCR.

## The taxonomy

`taxonomy.py` has the full list: 4 families, 20 root causes (POSITION 6, CASH 4, SETTLEMENT 4, TRADE 6).

## Why the model predicts root cause, not family

`check_ml_targets.py` fits the same three models on the same features against both targets:

| Target | Logistic Regression | Random Forest | XGBoost |
|---|---|---|---|
| Family (4 classes) | 0.657 | 1.000 | 1.000 |
| Root cause (20 classes) | 0.744 | 0.944 | 0.944 |

Family is close to a lookup of which table has a difference, so there is nothing to compare or tune. Root cause shows a real gap between models and isn't solved by any of them, so that's the target.

Most of what the tree models miss is the corporate-action pair. `CA_MANDATORY_NOT_REFLECTED` and `CA_VOLUNTARY_DECISION` were built to look the same in the numbers: in both the custodian still shows the pre-event quantity. The only way to tell them apart is the notice (`:22F::CAMV//MAND` or `VOLU`), which is what the RCA agent reads.

## Using real market data

`load_clean_trades()` in `generate_trade_breaks.py` is the only place to change:

1. Real prices and volumes from the NSE bhavcopy (for example via `NseIndiaApi`).
2. Real corporate actions (dividends, splits, bonuses, rights) instead of the fixed 1.5, 2 and 3 ratios.

nseindia.com blocks requests that don't come from a browser session, so download on your own machine.
