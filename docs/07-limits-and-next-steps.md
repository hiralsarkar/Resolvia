# 7. Limits and next steps

## What my build doesn't do

- **Synthetic data.** Every number here comes from generated data with clean faults and exactly one fault per broken trade. Real breaks are messier and often have more than one cause.
- **Simulated execution.** Fixes are applied to a copy of the records. Nothing touches a real settlement, trading or payment system.
- **A local database.** Cases, decisions and the audit trail are saved to a SQLite file. That survives restarts, but a bank would want a shared, managed database with an append-only trail.
- **No sign-in.** The operator ID is typed in. There's no authentication or role-based permissions behind the approval step.
- **The notice is usually there.** Every synthetic corporate action starts with a clean MT564. The stress tests damage and remove notices to see what happens (accuracy on corporate actions falls to 65% with none), but real notices fail in ways I haven't simulated, which is why every corporate action still goes to a person.

## What I'd add for production

1. **The bank's break feed** in place of the generator, plus real reference data: NSE bhavcopy prices and a corporate actions feed (see `load_clean_trades()` in `data/generate_trade_breaks.py`).
2. **A managed database** in place of the local SQLite file, with the audit trail made append-only at the database level.
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
python models/ml_classifier/build_production.py   # noise-trained, calibrated model + threshold
python embeddings/build_indices.py         # documents and CA rules
python knowledge/build_resolved_cases.py   # precedents, using those indexes
python embeddings/build_indices.py         # again, to index the precedents
python eval/baseline_comparison.py
python eval/pipeline_eval.py
python eval/robustness.py
python eval/approval_policy.py
python eval/extraction_eval.py
```

Next: [Responsible AI and governance](08-responsible-ai.md)
