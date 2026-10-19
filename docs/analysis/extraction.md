# Document extraction

Written by `backend/eval/extraction_eval.py`. Share of trades where each field was read correctly. Ground truth is `data/broker_confirms_mapping.csv`.

## rules

| document kind | trades | trade_id | symbol | quantity | price | counterparty | settlement_date |
|---|---|---|---|---|---|---|---|
| formal email | 46 | 100% | 100% | 100% | 100% | 100% | 100% |
| terse note | 34 | 100% | 100% | 100% | 100% | 100% | 100% |
| chat message | 39 | 100% | 100% | 100% | 100% | 0% | 100% |
| WhatsApp | 34 | 100% | 100% | 100% | 100% | 100% | 100% |
| scanned-style advice | 47 | 100% | 100% | 100% | 100% | 100% | 100% |
| batch email | 62 | 100% | 100% | 100% | 100% | 23% | 100% |
| contract note | 900 | 100% | 100% | 100% | 100% | 100% | 100% |
| all | 1162 | 100% | 100% | 100% | 100% | 92% | 100% |

## rules (2% character noise)

| document kind | trades | trade_id | symbol | quantity | price | counterparty | settlement_date |
|---|---|---|---|---|---|---|---|
| formal email | 46 | 96% | 74% | 83% | 65% | 89% | 74% |
| terse note | 34 | 82% | 68% | 68% | 76% | 65% | 59% |
| chat message | 39 | 77% | 67% | 59% | 59% | 0% | 38% |
| WhatsApp | 34 | 76% | 71% | 76% | 65% | 59% | 65% |
| scanned-style advice | 47 | 81% | 72% | 68% | 64% | 70% | 60% |
| batch email | 62 | 81% | 69% | 71% | 77% | 14% | 64% |
| contract note | 900 | 83% | 72% | 64% | 66% | 83% | 64% |
| all | 1162 | 83% | 72% | 66% | 67% | 75% | 63% |

## rules (5% character noise)

| document kind | trades | trade_id | symbol | quantity | price | counterparty | settlement_date |
|---|---|---|---|---|---|---|---|
| formal email | 46 | 85% | 67% | 63% | 41% | 70% | 39% |
| terse note | 34 | 71% | 47% | 56% | 47% | 50% | 44% |
| chat message | 39 | 72% | 54% | 38% | 33% | 0% | 10% |
| WhatsApp | 34 | 62% | 44% | 38% | 53% | 29% | 38% |
| scanned-style advice | 47 | 66% | 49% | 47% | 34% | 49% | 28% |
| batch email | 62 | 58% | 42% | 42% | 40% | 11% | 39% |
| contract note | 900 | 62% | 44% | 35% | 31% | 58% | 32% |
| all | 1162 | 64% | 46% | 38% | 33% | 53% | 33% |

The LLM column appears once the script is run with `--llm` and an OpenRouter key.
