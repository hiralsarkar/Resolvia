"""
Builds and runs docs/analysis/eda_notebook.ipynb. It's a script rather than a
hand-edited notebook so it can be regenerated whenever the generator changes.

Printed output sticks to plain ASCII: on Windows a Jupyter kernel running
under the default console codepage can mangle characters like the plus-minus
sign.
"""

import nbformat as nbf
from nbclient import NotebookClient

nb = nbf.v4.new_notebook()
cells = []

def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))

def code(text):
    cells.append(nbf.v4.new_code_cell(text))

md("# Resolvia: exploring the synthetic break data\n\nFour break families (used for routing) and 20 root causes (what the classifier predicts; see `check_ml_targets.py` for why). The data comes from `generate_trade_breaks.py` and is checked by `validate_dataset.py`.")

code("""
import pandas as pd
import matplotlib.pyplot as plt

trades = pd.read_csv("../data/trades.csv")
positions = pd.read_csv("../data/positions.csv")
cash = pd.read_csv("../data/cash_transactions.csv")
settlements = pd.read_csv("../data/settlements.csv")
breaks = pd.read_csv("../data/breaks.csv")

print("trades:", trades.shape)
print("positions:", positions.shape)
print("cash_transactions:", cash.shape)
print("settlements:", settlements.shape)
print("breaks:", breaks.shape)
""")

md("## 1. Break rate and families\n\nHalf the trades have a break. Real reconciliation sees more like 1 to 5%; the rate is high so each of the 20 root causes gets 150 examples. Families are for routing only and are not the model target (see section 4).")

code("""
break_rate = len(breaks) / len(trades)
print(f"Break rate: {break_rate:.1%} ({len(breaks)} of {len(trades)} trades)")

fam_counts = breaks["break_type"].value_counts()
print(fam_counts)

fig, ax = plt.subplots(figsize=(6, 4))
fam_counts.plot(kind="bar", ax=ax, color="#2b6cb0")
ax.set_title("Breaks by family")
ax.set_ylabel("count")
plt.tight_layout()
plt.show()
""")

md("**What this shows:** TRADE and POSITION are the biggest families because each has 6 root causes (the two confirmation causes sit under TRADE, the three corporate-action causes under POSITION). SETTLEMENT and CASH have 4 each. That follows directly from giving every root cause 150 breaks; it isn't a claim about real-world frequency, which would need real break logs.")

md("## 2. Root causes (the model target)")

code("""
rc_counts = breaks["mismatch_type"].value_counts()
print(rc_counts)

fig, ax = plt.subplots(figsize=(8, 6))
rc_counts.sort_values().plot(kind="barh", ax=ax, color="#2f855a")
ax.set_title("Breaks by root cause (20 classes)")
ax.set_xlabel("count")
plt.tight_layout()
plt.show()
""")

md("**What this shows:** 3,000 breaks spread evenly over 20 root causes gives about 30 test examples per class, enough to read per-class F1 with some confidence. The even split is a choice we made for training, not evidence that real breaks are evenly spread.")

md("## 3. Severity and corporate actions")

code("""
sev_counts = breaks["severity"].value_counts().reindex(["P0", "P1", "P2"])
print(sev_counts)

ca_counts = breaks["corporate_action_type"].fillna("").replace("", "NOT_CA").value_counts()
print(ca_counts)

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
sev_counts.plot(kind="bar", ax=axes[0], color="#c53030")
axes[0].set_title("Breaks by severity")
ca_counts.plot(kind="bar", ax=axes[1], color="#805ad5")
axes[1].set_title("Corporate-action breakdown")
plt.tight_layout()
plt.show()
""")

md("**What this shows:** P0 breaks come from 5 root causes: missing booking, missing cash entry, wrong SSI, missing instruction and missing confirmation. Those are the cases that can stop a payment, so they matter most for the approval flow. The 450 corporate-action breaks split into mandatory and voluntary; every voluntary one has to reach a person before anything changes.")

md("## 4. Why family is a poor model target and root cause isn't\n\nThe full experiment is in `check_ml_targets.py`. Logistic Regression, Random Forest and XGBoost were fitted on the same 15 features against both targets:")

code("""
import subprocess, sys
result = subprocess.run(
    [sys.executable, "check_ml_targets.py"],
    cwd="../data", capture_output=True, text=True,
)
print(result.stdout)
if result.returncode != 0:
    print("check_ml_targets.py FAILED, returncode", result.returncode)
    print(result.stderr)
""")

md("**What this shows:** both tree models score a perfect 1.000 on family. It's almost a lookup of which table has a difference, so there is nothing to compare or tune. Root cause is harder (about 0.93 for the tree models, with a real gap to Logistic Regression), so that's what the classifier is built around. Exact numbers are in `docs/analysis/model_comparison.md`.")

md("## 5. Do the features separate the root causes?\n\nA visual check of the quantity and cash differences by root cause, before trusting a single macro-F1 number.")

code("""
positions_idx = positions.set_index("trade_id")
breaks_pos = breaks[breaks["break_type"] == "POSITION"].copy()
breaks_pos["actual_qty"] = breaks_pos["source_record_id"].map(positions_idx["actual_quantity"])
breaks_pos["expected_qty"] = breaks_pos["source_record_id"].map(positions_idx["expected_quantity"])
breaks_pos["qty_ratio"] = breaks_pos["actual_qty"] / breaks_pos["expected_qty"]

fig, ax = plt.subplots(figsize=(8, 5))
breaks_pos.boxplot(column="qty_ratio", by="mismatch_type", ax=ax, rot=45)
ax.set_title("actual/expected quantity ratio by POSITION root cause")
plt.suptitle("")
plt.tight_layout()
plt.show()
""")

md("**What this shows:** `POS_MISSING_BOOKING` sits alone at a ratio of 0. The three corporate-action causes bunch together around the same few ratios because they all use the same split and bonus ratios (1.5, 2 and 3). That is exactly why the classifier can't separate them from the numbers alone, and why the notice has to be read.")

md("## 6. Class balance")

code("""
imbalance = breaks["mismatch_type"].value_counts()
print(f"Largest class: {imbalance.idxmax()} ({imbalance.max()} examples)")
print(f"Smallest class: {imbalance.idxmin()} ({imbalance.min()} examples)")
print(f"Ratio: {imbalance.max() / imbalance.min():.1f}x")
""")

md("**What this shows:** every root cause has exactly 150 breaks, so the imbalance ratio is 1.0. Macro-F1 is still the right metric because it weighs every class equally; the even balance is a training choice, not a statement about how often each break happens.")

nb["cells"] = cells

client = NotebookClient(nb, timeout=120, kernel_name="resolvia-venv")
client.execute()

import os
os.makedirs("../docs", exist_ok=True)
with open("../docs/analysis/eda_notebook.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print("Notebook written and executed: docs/analysis/eda_notebook.ipynb")
