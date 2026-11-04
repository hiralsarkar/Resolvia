"""
Builds the demo working day once, offline, into backend/knowledge/demo_day.db.

The app used to replay this day in a background thread every time the server
started. That ran a few hundred cases through the full pipeline on Streamlit
Cloud's small machine and starved the web server. Now the day is built here,
committed, and copied into place at startup (see store.py).

Run from the repo root:  python backend/build_demo_day.py
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "backend", "knowledge", "demo_day.db")
for sub in ("backend", "backend/agents", "backend/embeddings", "data", "frontend"):
    sys.path.insert(0, os.path.join(ROOT, sub))

if os.path.exists(OUT):
    os.remove(OUT)
os.environ["RESOLVIA_DB"] = OUT
os.environ["RESOLVIA_INVESTIGATOR"] = "off"

import demo_history  # noqa: E402
import store  # noqa: E402

picks = demo_history.plan()
print(f"working {len(picks)} cases", flush=True)
t = time.time()
demo_history.progress["planned"] = len(picks)
demo_history._run(picks)
p = demo_history.progress
print(f"done {p['done']} failed {p['failed']} in {time.time() - t:.0f}s; last error: {p['last_error']}", flush=True)
statuses = store.case_statuses()
print(f"{len(statuses)} cases stored", flush=True)
if p["failed"] > len(picks) * 0.05 or len(statuses) < 50:
    sys.exit("too many failures, not shipping this day")
store._conn().execute("VACUUM")
