# RESOLVIA

<p align="center">
  <strong>Investment Banking Exception Intelligence &amp; Resolution</strong><br>
  <em>From Break to Verified Resolution.</em>
</p>

<p align="center">
  <a href="https://resolvia.streamlit.app/"><img src="https://img.shields.io/badge/%E2%96%B6%20LIVE%20APP-RESOLVIA-18E6B5?style=for-the-badge&labelColor=0B0F16" alt="Live App"/></a>
  <a href="https://github.com/hiralsarkar/Resolvia"><img src="https://img.shields.io/badge/GitHub-Repository-18181B?style=for-the-badge&logo=github" alt="GitHub Repository"/></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white" alt="Streamlit"/>
  <img src="https://img.shields.io/badge/Scikit--learn-F7931E?style=flat-square&logo=scikit-learn&logoColor=white" alt="Scikit-learn"/>
  <img src="https://img.shields.io/badge/XGBoost-189B3A?style=flat-square&logo=xgboost&logoColor=white" alt="XGBoost"/>
  <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white" alt="PyTorch"/>
  <img src="https://img.shields.io/badge/Plotly-3F4F75?style=flat-square&logo=plotly&logoColor=white" alt="Plotly"/>
  <img src="https://img.shields.io/badge/Sentence--Transformers-6A5ACD?style=flat-square" alt="Sentence Transformers"/>
  <img src="https://img.shields.io/badge/EasyOCR-00A67E?style=flat-square" alt="EasyOCR"/>
  <img src="https://img.shields.io/badge/OpenRouter-111827?style=flat-square" alt="OpenRouter"/>
</p>

<p align="center">
  <img src="docs/resolvia-workflow.svg" alt="Resolvia exception intelligence workflow" width="100%"/>
</p>

## The idea

Post-trade reconciliation breaks are rarely difficult because the final fix is complicated. They are difficult because an analyst has to **find the evidence, connect the records, determine the root cause, assess the exposure, obtain authorization, execute the controlled fix, and verify the outcome**.

**Resolvia turns that workflow into a coordinated exception-resolution workbench.**

> **Records first. People decide. Every action is verified and auditable.**

It covers cash-equity exceptions across **trade, settlement, position, cash and corporate-action** workflows using a synthetic but format-realistic dataset.

### [▶ Open the live application →](https://resolvia.streamlit.app/)

---

## How a break moves through Resolvia

```
INTAKE
   ↓
EVIDENCE
   ↓
ROOT CAUSE
   ↓
RESOLUTION PATH
   ↓
HUMAN CONTROL  ← Review / Approve / Escalate
   ↓
ACTION
   ↓
VERIFICATION
   ↓
VERIFIED RESOLUTION
```

The **Orchestrator coordinates the stages; it does not make the decision itself.**

| Stage | What happens |
|---|---|
| 🔵 **Intake** | Routes the exception to a break family and assigns priority. |
| 🟣 **Evidence** | Retrieves trade records, settlement messages, contract notes, OCR evidence and similar precedent cases. |
| 🟢 **Root Cause** | Classifies the underlying cause across 20 root-cause classes and provides supporting evidence. |
| 🩷 **Resolution Path** | Determines the recommended remediation and quantifies exposure. |
| 🟠 **Human Control** | Enforces policy. Review, approval or escalation remains a human decision. |
| 🟢 **Verification** | Re-checks the records after the action and closes or reopens the case. |

---

## What makes it an exception-resolution workbench?

### Evidence before explanation
Investigation retrieves the relevant records and precedent cases before a resolution path is presented.

### Models + rules + retrieval
Resolvia combines machine-learning classification, deterministic policy logic, document/OCR extraction and semantic retrieval rather than relying on a single technique.

### Human control by design
The **Control Gate is policy code, not a model**. Exceptions requiring authorization stop until an operator chooses **Review, Approve or Escalate**.

### Resolution is not the finish line
A proposed fix is not treated as success. Resolvia performs a separate verification step to confirm whether the underlying break actually cleared.

### Built for three people
**Analyst:** clear next action, manual procedure, owner and evidence checklist.  
**Manager:** workload, ageing, exposure, categories and items requiring attention.  
**Auditor:** Operations ID, timestamp, action and case history by break.

---

## Technical stack

| Layer | Technologies |
|---|---|
| **Application** | Python · Streamlit |
| **Machine Learning** | Scikit-learn · XGBoost · PyTorch |
| **NLP / Retrieval** | Sentence Transformers · NumPy-based embedding indices |
| **Document Intelligence** | EasyOCR · SWIFT / contract-note extraction |
| **Analytics** | Pandas · Plotly · Matplotlib |
| **LLM Layer** | OpenRouter · configurable model fallback |
| **Workflow** | Python Orchestrator · deterministic Control Gate |
| **Data / Evaluation** | Synthetic trade-break generator · model evaluation pipeline |

The optional narrative layer is not required for the core investigation, classification, policy and verification workflow.

---

## Results

| Metric | Result |
|---|---:|
| Trades / breaks | **6,000 / 3,000** |
| Root-cause classifier — test macro-F1 | **0.933** |
| Rules-only baseline — macro-F1 | **0.820** |
| Break-family classifier | **1.000** |
| OCR accuracy on scanned confirms | **~99%** |
| Precedent cases | **400** |
| Precedent outcomes | **380 closed · 20 reopened** |

See [`docs/model_comparison.md`](docs/model_comparison.md) for the detailed model comparison and [`docs/eda_notebook.ipynb`](docs/eda_notebook.ipynb) for the exploratory analysis.

---

## Application flow

1. **Home** — see the operational workload and items needing attention.
2. **Break Queue** — find and prioritize an exception.
3. **Case Workspace** — review evidence, cause, ownership and current status.
4. **Resolution** — review the proposed path and record the human decision.
5. **Manual Guide** — follow the practical resolution procedure when the fix is carried out manually.
6. **Audit Trail** — trace every recorded action by Operations ID, timestamp and break.
7. **Manager Overview** — inspect arrivals, open work, ageing, resolution volume, exposure and categories.

---

## Run locally

Python **3.10+** is recommended.

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

cd ..
streamlit run frontend/app.py
```

The first analysis can take around 20 seconds while models and retrieval indices load. Subsequent cases are faster.

For the optional narrative layer, copy `.env.example` to `.env` and set `OPENROUTER_API_KEY`. `OPENROUTER_MODEL` can be configured as a comma-separated fallback list.

---

## Rebuilding the data and models

Generators run from `data/`; model and retrieval builds run from `backend/`.

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

---

## Repository structure

```
data/       Synthetic data generation, taxonomy, validation, EDA
backend/    Agents, orchestrator, control gate, models, OCR, retrieval, evaluation
frontend/   Streamlit application, theme, workbench and interaction layer
docs/       Proposal, project pitch, EDA, model comparison and workflow visual
```

---

## Known limits

- Application state is held in memory, so cases reset when the server restarts.
- The repair step is simulated; no real settlement or trading system is modified.
- The dataset is synthetic and designed for realistic workflow demonstration.
- Production deployment would require persistent state, enterprise data controls, authentication, audit infrastructure and integration with real post-trade systems.

---

<p align="center">
  <strong>RESOLVIA</strong><br/>
  <sub>Investment Banking Exception Intelligence &amp; Resolution</sub>
</p>
