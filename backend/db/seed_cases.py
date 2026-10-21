"""
seed_cases.py - builds backend/db/seed/resolvia_seed.db, the starting state the
app opens with.

About a quarter of the 3,000 breaks are worked through the REAL pipeline
(orchestrator + control gate + validation, via backend/workflow.py - the same
functions the Streamlit screens call) the way an operations team would have
worked them over the reconciliation window:

  * administrative (PROPOSAL-tier) fixes close under policy after validation
  * controlled actions are approved by a named approver, executed, validated
  * some corrections are done by hand: start -> record action + evidence
    reference -> verified by a different person (four-eyes) -> closed
  * voluntary corporate actions reopen after the automated attempt (by design)
    and are then closed manually once the client election is recorded
  * a smaller set is left mid-flight: waiting for approval, in review,
    escalated, manual correction in progress, waiting for verification,
    reopened

Every step lands in the case history and the operational audit trail with a
back-dated timestamp (the break's business date plus realistic working time),
so the Audit Trail screen shows a believable history from the first launch.

Nothing about the outcome is invented here: root cause, proposal, authority
tier, gate decision and validation result all come from the agents. The seeder
only plays the humans (who approved, when, with what note).

Run from the repo root:
    python backend/db/seed_cases.py            # default: 25% resolved
    python backend/db/seed_cases.py --resolved 0.22
"""

import argparse
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
SEED_PATH = os.path.join(HERE, "seed", "resolvia_seed.db")

# Must be set before case_store is imported anywhere.
os.environ["RESOLVIA_DB"] = SEED_PATH
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "agents"))

IST = timezone(timedelta(hours=5, minutes=30))
WINDOW_END = datetime(2026, 8, 22, 21, 0, tzinfo=IST)  # last business date in the snapshot, evening

ANALYSTS = ["OPS-1047", "OPS-1182", "OPS-1309", "OPS-1426", "OPS-1533"]
APPROVERS = ["OPS-2210", "OPS-2275", "OPS-2318"]
VERIFIERS = ["OPS-3051", "OPS-3088", "OPS-3112"]

# Left mid-flight so the queue, approvals and manager views have live work.
IN_FLIGHT = {"AWAITING_APPROVAL": 55, "IN_REVIEW": 15, "ESCALATED": 20,
             "MANUAL_IN_PROGRESS": 12, "AWAITING_VERIFICATION": 10, "REOPENED": 12}

NOTES = {
    "SETTLEMENT": ["Checked booked SSI against the SSI master; custodian confirmed {ref}",
                   "Custodian status call logged under {ref}; instruction details verified",
                   "Settlement date and account agreed with counterparty ops ({ref})"],
    "CASH": ["Posted amount agreed to bank statement line {ref}",
             "Cash ops confirmed posting source; correction ticket {ref}",
             "Value date and currency checked against custodian advice {ref}"],
    "TRADE": ["Booking agreed to broker contract note; counterparty confirmation {ref}",
              "Trade economics confirmed with front office, ticket {ref}",
              "Matched to electronic confirm; middle-office ref {ref}"],
    "POSITION": ["Holding agreed to custodian position report {ref}",
                 "Position control confirmed the booking gap; ref {ref}",
                 "Depository statement checked; adjustment ticket {ref}"],
    "CA": ["Corporate action notice and entitlement checked; ref {ref}",
           "Client election received and logged under {ref}",
           "Registrar confirmation for the CA ratio, ref {ref}"],
}
MANUAL_ACTIONS = {
    "SETTLEMENT": "Amended the settlement instruction in the settlement system after custodian confirmation",
    "CASH": "Raised and posted the approved cash correction in the ledger",
    "TRADE": "Amended the booking in the trade capture system to the confirmed details",
    "POSITION": "Booked the position adjustment through Position Control",
    "CA": "Recorded the client election and booked the entitlement adjustment",
}


class ScriptClock:
    """Ticks forward a few seconds every time anything asks for 'now'."""

    def __init__(self, rng):
        self.rng = rng
        self.t = None

    def __call__(self):
        self.t += timedelta(seconds=self.rng.randint(1, 9))
        return self.t

    def start(self, business_date):
        d = datetime.strptime(business_date, "%Y-%m-%d")
        self.t = datetime(d.year, d.month, d.day, self.rng.randint(9, 15), self.rng.randint(0, 59),
                          self.rng.randint(0, 59), tzinfo=IST)

    def wait(self, lo_minutes, hi_minutes):
        self.t += timedelta(minutes=self.rng.uniform(lo_minutes, hi_minutes))
        local = self.t.astimezone(IST)
        if local.hour >= 19 or local.hour < 9:   # people work desk hours: carry over to next morning
            nxt = (local + timedelta(days=1)) if local.hour >= 19 else local
            self.t = nxt.replace(hour=9, minute=self.rng.randint(15, 59), second=self.rng.randint(0, 59))
        if self.t > WINDOW_END:
            self.t = WINDOW_END - timedelta(minutes=self.rng.uniform(1, 90))


def _family(b):
    return "CA" if b["corporate_action_type"] else b["break_type"]


def _ref(rng, b):
    prefix = {"SETTLEMENT": "CUS", "CASH": "BNK", "TRADE": "CNF", "POSITION": "POS", "CA": "CAE"}[_family(b)]
    return f"{prefix}-{rng.randint(100000, 999999)}"


def _note(rng, b):
    return rng.choice(NOTES[_family(b)]).format(ref=_ref(rng, b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolved", type=float, default=0.25, help="share of breaks to leave CLOSED")
    ap.add_argument("--seed", type=int, default=20260822)
    args = ap.parse_args()

    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(SEED_PATH + suffix):
            os.remove(SEED_PATH + suffix)
    os.makedirs(os.path.dirname(SEED_PATH), exist_ok=True)

    import case_store
    import clock
    import orchestrator
    import workflow
    from audit import record as audit
    from investigation import _tables

    assert case_store.path() == SEED_PATH, case_store.path()
    rng = random.Random(args.seed)
    clk = ScriptClock(rng)
    clock.set_source(clk)

    breaks = _tables()["breaks"]
    n_total = len(breaks)
    n_closed_target = round(n_total * args.resolved)

    import json
    with open(os.path.join(BACKEND, "knowledge", "resolved_cases.json"), encoding="utf-8") as f:
        precedent_ids = {c["break_id"] for c in json.load(f)}

    # Stratify by root cause so every kind of break has resolved history.
    by_cause = defaultdict(list)
    for bid, b in breaks.items():
        by_cause[b["mismatch_type"]].append(bid)
    causes = sorted(by_cause)
    per_cause = {c: n_closed_target // len(causes) for c in causes}
    for c in rng.sample(causes, n_closed_target % len(causes)):
        per_cause[c] += 1

    to_close = []
    for c in causes:
        ids = sorted(by_cause[c])
        first = [b for b in ids if b in precedent_ids]   # the precedent corpus is "past resolved work"
        rest = [b for b in ids if b not in precedent_ids]
        rng.shuffle(rest)
        to_close += (first + rest)[: per_cause[c]]
    chosen = set(to_close)

    # In-flight work comes from the last few business days and from causes that need
    # a human (administrative PROPOSAL-tier fixes would simply close on review).
    from resolution import ACTION_CATALOG
    def _needs_human(bid):
        return ACTION_CATALOG[breaks[bid]["mismatch_type"]][2] == "CONTROLLED_ACTION"
    recent = sorted(b for b in breaks if b not in chosen and breaks[b]["business_date"] >= "2026-08-18"
                    and _needs_human(b))
    rng.shuffle(recent)
    in_flight = []
    for status, n in IN_FLIGHT.items():
        for _ in range(n):
            if status == "REOPENED":   # only a voluntary CA reopens after an approved automated fix
                pick = next(b for b in recent if breaks[b]["mismatch_type"] == "CA_VOLUNTARY_DECISION")
            else:
                pick = next(b for b in recent if breaks[b]["mismatch_type"] != "CA_VOLUNTARY_DECISION")
            recent.remove(pick)
            in_flight.append((pick, status))

    work = [(b, "CLOSED") for b in to_close] + in_flight
    work.sort(key=lambda x: (breaks[x[0]]["business_date"], x[0]))  # process in calendar order

    outcome = Counter()
    modes = Counter()
    for i, (bid, target) in enumerate(work, 1):
        b = breaks[bid]
        analyst, approver, verifier = rng.choice(ANALYSTS), rng.choice(APPROVERS), rng.choice(VERIFIERS)
        clk.start(b["business_date"])
        audit(analyst, "BREAK_OPENED", bid, "Analyst opened the break")
        case = workflow.start_case(bid, analyst)
        status = case["status"]

        if status == "HALTED_DATA_QUALITY":
            outcome[status] += 1
            continue

        if target != "CLOSED" and status == "CLOSED":
            outcome["CLOSED"] += 1            # policy-tier fix closes on its own; that's fine
            modes["policy"] += 1
            continue

        clk.wait(5, 90)
        audit(analyst, "RESOLUTION_GUIDE_OPENED", bid, "Analyst opened the manual resolution guide")

        if target == "CLOSED":
            if status == "CLOSED":
                modes["policy"] += 1
            else:
                is_voluntary_ca = b["mismatch_type"] == "CA_VOLUNTARY_DECISION"
                manual = is_voluntary_ca and rng.random() < 0.5 or (not is_voluntary_ca and rng.random() < 0.28)
                if rng.random() < 0.12:
                    clk.wait(20, 240)
                    workflow.mark(bid, "ESCALATED", analyst, "Exposure above desk limit - sending to manager")
                if not manual:
                    clk.wait(10, 600)
                    case = workflow.approve(bid, approver, _note(rng, b), mode="Assisted")
                    modes["assisted"] += 1
                if case["status"] == "REOPENED" or manual:
                    clk.wait(30, 900)
                    workflow.begin_manual(bid, analyst, "Correcting in the owning system" if not
                                          case["status"] == "REOPENED" else "Automated fix did not hold - correcting manually")
                    clk.wait(20, 480)
                    workflow.submit_manual(bid, analyst, MANUAL_ACTIONS[_family(b)], _ref(rng, b), [True, True, True])
                    clk.wait(15, 600)
                    workflow.verify_manual(bid, verifier, _note(rng, b) + "; source record now agrees")
                    modes["manual"] += 1
            outcome[orchestrator.get_case(bid)["status"]] += 1
            continue

        # ---- left in flight
        if target == "AWAITING_APPROVAL":
            pass
        elif target in ("IN_REVIEW", "ESCALATED"):
            workflow.mark(bid, target, analyst, "Needs a closer look at the counterparty confirmation"
                          if target == "IN_REVIEW" else "Exposure above desk limit - sending to manager")
        elif target in ("MANUAL_IN_PROGRESS", "AWAITING_VERIFICATION"):
            workflow.begin_manual(bid, analyst, "Correcting in the owning system")
            if target == "AWAITING_VERIFICATION":
                clk.wait(20, 300)
                workflow.submit_manual(bid, analyst, MANUAL_ACTIONS[_family(b)], _ref(rng, b), [True, True, True])
        elif target == "REOPENED":
            workflow.approve(bid, approver, _note(rng, b), mode="Assisted")
        outcome[orchestrator.get_case(bid)["status"]] += 1

        if i % 100 == 0:
            print(f"  {i}/{len(work)} processed", flush=True)

    clock.set_source(None)
    counts = Counter(c["status"] for c in orchestrator._CASES.values())
    case_store.set_meta("seed", {"generated_by": "backend/db/seed_cases.py", "seed": args.seed,
                                 "total_breaks": n_total, "statuses": dict(counts),
                                 "resolution_modes": dict(modes)})
    # Fold the WAL into the main file so the committed seed is a single file.
    case_store._conn().execute("PRAGMA wal_checkpoint(TRUNCATE)")
    case_store._conn().execute("VACUUM")
    case_store._conn().close()

    print(f"\nSeeded {sum(counts.values())} cases into {SEED_PATH}")
    for k, v in counts.most_common():
        print(f"  {k:24s} {v:5d}  ({v / n_total:.1%} of all breaks)")
    print("Resolution modes for closed cases:", dict(modes))


if __name__ == "__main__":
    main()
