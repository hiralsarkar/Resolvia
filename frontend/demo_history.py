"""
A working day for the demo.

When the app starts with a near-empty case store, a background thread works a
random share of each family's breaks through the real pipeline, the way a
desk would: an analyst opens the case, the agents run, and an approver
approves, rejects or escalates it. Every step lands in the case history and
the audit trail with the person's ID, so the Break Queue, the Manager
Overview and the Audit Trail all show a desk part-way through its day.

Arrival ages follow a realistic shape: most breaks are from today or the last
day or two, and very few are older than four days. Every random choice is
seeded, so each restart replays the same day.
"""

import os
import random
import threading

import audit
import control_gate
import investigator
import orchestrator
import store
from investigation import DATA_DIR, _document_for, _tables

SEED = 2026
SHARE = (0.05, 0.13)  # each family gets its own share of breaks worked, in this range
AGE_WEIGHTS = [44, 22, 14, 9, 6, 3, 2]  # 0 to 6 days old
ANALYSTS = ["OPS-1047", "OPS-2210", "OPS-3318", "OPS-4102", "OPS-5526"]
APPROVERS = ["OPS-HEAD-01", "OPS-HEAD-02", "OPS-HEAD-03"]
OUTCOMES = [("approve", 80), ("leave", 11), ("escalate", 5), ("reject", 4)]

_started = False
_lock = threading.Lock()
progress = {"planned": 0, "done": 0, "failed": 0, "last_error": ""}


def age_days(break_id):
    """How many days ago this break arrived. Fixed per break."""
    return random.Random(f"{SEED}:age:{break_id}").choices(range(len(AGE_WEIGHTS)), weights=AGE_WEIGHTS)[0]


def _readable(break_id):
    """Skips breaks whose only document is a scan, so the day replays quickly."""
    doc = _document_for(break_id)
    return doc is None or os.path.exists(os.path.join(DATA_DIR, "broker_confirms", f"{doc['doc_id']}.txt"))


def plan():
    rng = random.Random(SEED)
    by_family = {}
    for bid, b in _tables()["breaks"].items():
        by_family.setdefault(b["break_type"], []).append(bid)
    picks = []
    for family in sorted(by_family):
        share = rng.uniform(*SHARE)
        # older breaks are much more likely to have been worked already
        pool = [b for b in by_family[family] if _readable(b)]
        weights = [1 + 3 * min(age_days(b), 3) for b in pool]
        chosen = set()
        while len(chosen) < int(share * len(by_family[family])):
            chosen.add(rng.choices(pool, weights=weights)[0])
        picks += [(b, rng.choices([o for o, _ in OUTCOMES], weights=[w for _, w in OUTCOMES])[0]) for b in sorted(chosen)]
    rng.shuffle(picks)
    return picks


def _sync(case, bid):
    for i, e in enumerate(case.get("history", [])):
        audit.record("SYSTEM", e.get("event", "SYSTEM_EVENT"), bid, e.get("detail", ""), source="CASE_PIPELINE",
                     dedupe_key=f"case:{bid}:history:{i}:{e.get('event')}:{e.get('timestamp')}")


def _work(bid, outcome, rng):
    analyst = rng.choice(ANALYSTS)
    audit.record(analyst, "CASE_ANALYSIS_STARTED", bid, "Analyst started the case pipeline")
    case = orchestrator.create_case(bid)
    if case["status"] == "AWAITING_APPROVAL" and outcome != "leave":
        approver = rng.choice(APPROVERS)
        if outcome == "approve":
            audit.record(approver, "APPROVAL_GRANTED", bid, f"Approved by {approver}; execution mode: Controlled Action")
            control_gate.record_decision(bid, "APPROVE", approver, "[Controlled Action] evidence checked")
            case["execution_mode"] = "Controlled Action"
            orchestrator._log(case, "EXECUTION_MODE", "Controlled Action")
            case = orchestrator.resume_case(bid)
        elif outcome == "reject":
            audit.record(approver, "APPROVAL_REJECTED", bid, f"Rejected by {approver}; notes: evidence incomplete")
            control_gate.record_decision(bid, "REJECT", approver, "evidence incomplete")
            case = orchestrator.resume_case(bid)
        else:
            audit.record(approver, "CASE_ESCALATED", bid, f"ESCALATED by {approver}; notes: exposure above desk limit")
            case["status"] = "ESCALATED"
            orchestrator._log(case, "HUMAN_ESCALATED", f"by {approver}: exposure above desk limit")
            orchestrator.save(case)
    _sync(case, bid)


def _run(picks):
    investigator.QUIET.on = True
    rng = random.Random(SEED + 1)
    for bid, outcome in picks:
        try:
            if orchestrator.get_case(bid) is None:
                _work(bid, outcome, rng)
        except Exception as e:  # one bad case shouldn't stop the day
            progress["failed"] += 1
            progress["last_error"] = f"{bid}: {type(e).__name__}: {e}"[:300]
        progress["done"] += 1


def start():
    """Starts the background day once per process, unless the store already has a day's work in it."""
    global _started
    if os.environ.get("RESOLVIA_DEMO_HISTORY", "on") == "off":
        return
    with _lock:
        if _started:
            return
        _started = True
        if len(store.case_statuses()) >= 50:
            return
        picks = plan()
        progress["planned"] = len(picks)
        threading.Thread(target=_run, args=(picks,), daemon=True, name="demo-history").start()
