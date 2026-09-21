# Resolvia

Post-trade reconciliation breaks are slow and repetitive to work by hand: someone
has to find the evidence, work out why the two sides disagree, decide on a fix,
get it signed off and then check the fix actually held. Resolvia is a prototype
that does the investigation for you and keeps a person in charge of the decision.

> AI investigates. Humans authorize. Systems execute. AI validates.

It covers cash-equity exceptions (trade, settlement, position and cash breaks,
plus corporate-action cases) on a synthetic but format-realistic dataset.

## How a case moves

```
Triage -> Investigation -> Root Cause -> Resolution Proposal -> Control Gate -> Validation
                       (all coordinated by the Orchestrator)
```

- **Triage** routes the break to a family and sets severity.
- **Investigation** pulls the related documents (SWIFT MT564/MT54x messages,
  NSE contract notes, OCR'd scans) and similar past cases. It retrieves only;
  it never judges.
- **Root Cause** picks one of 20 causes with a confidence score and ranked alternatives.
- **Resolution Proposal** writes the recommended fix and works out the exposure.
- **Control Gate** is plain policy code, not a model. Anything that needs approval
  stops here until a person decides: Review, Approve or Escalate. An approved fix
  is then carried out either as a controlled action or manually by an analyst.
- **Validation** re-checks the position after the fix and closes or reopens the case.

The Orchestrator only routes work between stages. It does not decide anything itself.

## Running it

Python 3.10+ is recommended.

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cd ..
streamlit run frontend/app.py
```

The first analysis takes around 20 seconds while the models and indices load.
After that it is quick.

Torch is pinned in `requirements.txt` because newer builds were blocked by a
Windows Application Control policy on my machine. If you are on a different
setup you can probably loosen it.

The narrative layers (document extraction and the written root-cause summary)
use OpenRouter and run only if `OPENROUTER_API_KEY` is set. Copy `.env.example` to
`.env` and fill it in (optionally set `OPENROUTER_MODEL` too; it defaults to a list of free models that are
tried in order, since free tiers rate-limit). Everything else
runs offline.

## The app

1. **Home** shows the six stations working through a case.
2. **Choose an exception** lists the breaks; pick one.
3. **Watch the analysis** runs the real pipeline with a live feed.
4. **Make the decision** is where a person reviews, approves or escalates.
5. **Overall results** shows the system's track record and the model numbers.

## Results

| | |
|---|---|
| Trades / breaks | 6,000 / 3,000 (break rate is deliberately high for training) |
| Root-cause classifier, test macro-F1 | 0.933 (RandomForest, 20 classes) |
| Rules-only baseline, macro-F1 | 0.820 |
| Break-family classifier | 1.000 (close to a lookup, used for routing only) |
| OCR accuracy on scanned confirms | about 99% |
| Precedent cases | 400 (380 closed, 20 reopened) |

`docs/model_comparison.md` has the full model comparison, and
`docs/eda_notebook.ipynb` has the data exploration.

## Rebuilding the data and models

Generators run from `data/`, the rest from `backend/`:

```bash
cd data
python generate_trade_breaks.py
python generate_broker_confirms.py
python render_scanned_images.py
python validate_dataset.py

cd ../backend
python embeddings/build_indices.py
python models/family_classifier/train.py
python models/ml_classifier/train.py
python knowledge/build_resolved_cases.py
python eval/baseline_comparison.py
```

## Layout

```
data/       taxonomy, generators, validation, EDA notebook builder
backend/    agents, orchestrator, control gate, models, OCR, embeddings, eval
frontend/   Streamlit app (theme, views, home-page animation)
docs/       proposal, pitch, EDA notebook, model comparison
```

## Known limits

- State is held in memory, so cases reset when the server restarts.
- The repair step is simulated; nothing is written to a real system.
- The data is synthetic. Swapping in real exchange data is the obvious next step.
