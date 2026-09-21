# Resolvia Data Schema (v7)

Replaces the old single "two-sided pair" schema (`train.csv`/`test.csv`
with one row per side per trade). See `check_ml_targets.py` for the empirical
justification of the ML target below.

## Why synthetic
No public dataset of real trade breaks exists - trade and reconciliation
data is confidential everywhere (banks, custodians, brokers). Same
approach as PaySim for fraud detection: simulate realistic operational
data, inject the anomaly, keep the ground truth.

## Design principle: this generator plays "the existing reconciliation
system." Per the v7 plan (Section 3), Resolvia itself does not do
matching/detection - it receives BREAK INPUT. `generate_trade_breaks.py`
is what produces that feed for this build; `backend/agents/matching.py`
plays the same role as an alternative/complementary generator (it detects
breaks from two-sided data rather than injecting them directly - kept for
that purpose, not part of the Resolvia pipeline itself).

## Tables

All five files live in this directory, each with a `split` column
(`TRAIN`/`TEST`, 80/20 by `trade_id`, deterministic under `random.seed(42)`).

### `trades.csv` - one row per trade, the internal/booked view
| Column | Meaning |
|---|---|
| trade_id | Primary key |
| trade_date, settlement_date | T / T+1 (India) |
| security, isin, ticker | Instrument identifiers |
| quantity, price, trade_value | Trade economics as booked |
| counterparty, portfolio | Booking parties |
| booking_status | Always BOOKED in this build |
| side | BUY/SELL |
| confirmed_price, confirmed_quantity, confirmed_trade_date, confirmed_counterparty | The **external confirmation** view - matches the booked columns unless a TRADE-family break is injected. Needed so TRADE-family breaks are independently observable rather than only existing on the `breaks` row (which would leak the label into the "features"). |
| confirmation_status | RECEIVED, or MISSING for `CONF_MISSING` |

### `positions.csv` - one row per trade, the observed/custodian position
| Column | Meaning |
|---|---|
| position_id | Primary key |
| trade_id | FK -> trades |
| security, portfolio | Denormalized for convenience |
| expected_quantity | = trades.quantity |
| actual_quantity | Observed externally - diverges for POSITION-family breaks (including all 3 corporate-action root causes) |
| as_of_date | Diverges for `POS_TIMING_DIFFERENCE` |
| source | CUSTODIAN, or MISSING for `POS_MISSING_BOOKING` |

### `cash_transactions.csv` - 0, 1, or 2 rows per trade
| Column | Meaning |
|---|---|
| cash_id | Primary key |
| trade_id | FK -> trades |
| account, currency | Where/what currency the cash posted in - currency diverges for `CASH_FX_INPUT_DIFFERENCE` |
| amount | Actual posted amount |
| expected_amount | = trades.trade_value |
| value_date, transaction_type, status | Operational metadata |

Row count is 1 for a clean trade, **0** for `CASH_MISSING_ENTRY` (the
movement never posted), **2** for `CASH_DUPLICATE_ENTRY`.

### `settlements.csv` - one row per trade, the observed settlement state
| Column | Meaning |
|---|---|
| settlement_id | Primary key |
| trade_id | FK -> trades |
| settlement_date | Diverges for `SETL_LATE_COUNTERPARTY` (+2-5d, status PENDING) and `SETL_INCORRECT_DATE` (+1d, status stays SETTLED) |
| settlement_status | SETTLED / PENDING / FAILED |
| instruction_status | INSTRUCTED / MISSING / INCORRECT |
| custodian | = trades.counterparty |
| quantity, amount | Settled quantity/amount |
| ssi_code | Standing settlement instruction actually used - diverges for `SETL_WRONG_SSI` (the payment-failure flagship scenario) |

### `breaks.csv` - one row per trade that has an injected break (50% of trades - deliberately inflated vs. real production break rates (~1-5%) to densify per-root-cause training/test examples to 150 each; see generate_trade_breaks.py's `__main__` comment)
| Column | Meaning |
|---|---|
| break_id | Primary key |
| reconciliation_id, business_date | Batch metadata |
| break_type | One of 4 families: POSITION / CASH / SETTLEMENT / TRADE - **routing only, not the ML target** (see below) |
| mismatch_type | The root cause key (e.g. `SETL_WRONG_SSI`) - **the actual classification target** |
| root_cause | Human-readable description of mismatch_type |
| source_system, comparison_system | Which two systems disagree |
| source_record_id, comparison_record_id | Both = trade_id in this build (breaks are trade-scoped) |
| source_value, target_value | The specific values that disagree |
| breaking_fields | Which column(s) diverged |
| severity | P0 (critical/settlement risk) / P1 / P2 |
| status | OPEN for every row in this generator - lifecycle (RESOLVED/REOPENED) comes from later weeks' Orchestrator/Validation Agent |
| age | 0 in this generator - a real "days open" clock starts once cases have a lifecycle |
| counterparty, client | = trades.counterparty / trades.portfolio |
| corporate_action_type | MANDATORY / VOLUNTARY / "" - only set for the 3 CA root causes. `VOLUNTARY` is where the hardcoded "always escalate to a human regardless of confidence" rule attaches (v7 Section 7/27) |
| needs_evidence_bundle | True for 100% of CA/SETTLEMENT/TRADE breaks (a contract note / settlement message / CA notice is generated for every relevant real-world event) plus a 25% sample of POSITION-non-CA/CASH breaks (an ops note only exists when someone wrote one) - 2212/3000 breaks at current volume. See generate_broker_confirms.py for the SWIFT MT564/MT54x-style and NSE contract-note-style document formats used per family. |

## The 20-root-cause taxonomy

See `taxonomy.py` (`ROOT_CAUSES` dict) for the authoritative list -
4 families x 20 root causes total (POSITION 6, CASH 4, SETTLEMENT 4,
TRADE 6 including the 2 confirmation-specific causes).

## ML target: root_cause, not break_type (Open Issue #1, resolved empirically)

`check_ml_targets.py` fits the same 3 candidate models (LogisticRegression,
RandomForest, XGBoost) against both targets on identical engineered
features:

| Target | LogReg | RandomForest | XGBoost |
|---|---|---|---|
| break_type (4 classes) | 0.657 | **1.000** | **1.000** |
| root_cause (20 classes) | 0.744 | 0.944 | 0.944 |

The 4-class target is a lookup table (perfect separation for both tree
models - nothing to compare, nothing to tune). root_cause is genuinely
harder: a real ~0.2 gap between LogReg and the tree models, and neither
tree model is perfect, which is exactly what a legitimate Model
Comparison / Model Tuning steps need. **Week 2's classifier
predicts root_cause; break_type is used only for routing to the right
investigation path.**

One deliberate exception: `CA_MANDATORY_NOT_REFLECTED` and
`CA_VOLUNTARY_DECISION` are constructed to be structurally
indistinguishable from engineered numeric features alone (both look like
"quantity reverted to its pre-ratio value") - telling them apart is
supposed to require reading the corporate action notice itself, which is
Week 2+ document evidence, not something a structured classifier should
be able to do. This is very likely most of where root_cause's 0.944
(vs a hypothetical ~1.0) comes from, and that's intentional, not a bug -
it's the reason the CA judgment step in the original plan needed an LLM
step at all.

## Swapping in real data (recommended before the final demo)
Replace `load_clean_trades()` in `generate_trade_breaks.py` with a loader
for real NSE data (free, no paid license):
1. **NSE Bhavcopy** (real daily prices/quantities) via `NseIndiaApi` or
   `bhavCopy-downloader` on GitHub.
2. **Corporate actions** (real dividends/splits/bonuses/rights) via
   `pip install india-corp-actions` - use real ratios/ex-dates instead of
   the fixed {1.5, 2.0, 3.0} demo ratios.

nseindia.com blocks non-browser requests without a session/cookie
handshake - run the download step on your own machine, not in a
sandboxed tool-use environment.
