# 7. Limits and next steps

## What this build doesn't do

- **Synthetic data.** Every number here comes from generated data with clean faults and exactly one fault per broken trade. Real breaks are messier and often have more than one cause.
- **Simulated execution.** Fixes are applied to a copy of the records. Nothing touches a real settlement, trading or payment system.
- **In-memory cases.** The app keeps open cases in memory, so they reset when the server restarts. The audit log is a local file.
- **No sign-in.** The operator ID is typed in. There's no authentication or role-based permissions behind the approval step.
- **The notice is always there.** Every synthetic corporate action has a clean MT564 with a CAMV field. In real life the notice may be late, missing or a scan, and that case should fall back to a person, which the system already requires for every corporate action.

## What a production version would need

1. **The bank's break feed** in place of the generator, plus real reference data: NSE bhavcopy prices and a corporate actions feed (see `load_clean_trades()` in `data/generate_trade_breaks.py`).
2. **A database** for cases, decisions and the audit trail, with the trail made append-only.
3. **Sign-in and roles**, so approval rights come from the bank's directory and a maker can't check their own work.
4. **The gate wired into existing maker-checker tooling** instead of its own decision store.
5. **Validation against live records** after the real system applies a fix.
6. **Multi-cause breaks and drift monitoring**, since a model trained on one fault per trade will see combinations it never learned.

## Rebuilding what's here

```bash
cd data
python generate_trade_breaks.py
python generate_broker_confirms.py
python render_scanned_images.py
python validate_dataset.py

cd ../backend
python models/family_classifier/train.py
python models/ml_classifier/train.py
python embeddings/build_indices.py         # documents and CA rules
python knowledge/build_resolved_cases.py   # precedents, using those indexes
python embeddings/build_indices.py         # again, to index the precedents
python eval/baseline_comparison.py
python eval/pipeline_eval.py
```

Back to [the tour](README.md)
