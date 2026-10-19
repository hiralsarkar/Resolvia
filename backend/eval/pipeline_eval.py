"""
End-to-end evaluation on the held-out TEST breaks.

The model comparison (models/ml_classifier/train.py) scores the classifier on
its own. This scores the whole system the way it actually runs: every TEST
break goes through the Orchestrator, controlled actions are approved, and I
count what comes out the other end.

Reports
  - root-cause macro-F1 for the model alone vs the RCA agent (model plus the
    corporate-action notice check)
  - how many breaks needed a person before anything ran
  - final outcomes: CLOSED, REOPENED, ON_HOLD
  - unauthorised executions, which should always be zero

Run from backend/:  python eval/pipeline_eval.py
"""

import os
import sys
from collections import Counter

from sklearn.metrics import f1_score


# batch runs use a throwaway database, never the real audit trail
os.environ.setdefault("RESOLVIA_DB", ":memory:")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "agents"))

import control_gate  # noqa: E402
import orchestrator  # noqa: E402
import rca  # noqa: E402
from investigation import _tables  # noqa: E402


def main():
    control_gate.reset()
    orchestrator.reset()
    breaks = {bid: b for bid, b in _tables()["breaks"].items() if b["split"] == "TEST"}

    truth, model_only, agent = [], [], []
    needed_person, outcomes, unauthorised = 0, Counter(), 0

    for bid, b in breaks.items():
        case = orchestrator.create_case(bid)
        if case["status"] == "AWAITING_APPROVAL":
            needed_person += 1
            if case["post_execution"] is not None:
                unauthorised += 1
            control_gate.record_decision(bid, "APPROVE", "eval@resolvia.local")
            case = orchestrator.resume_case(bid)

        truth.append(b["mismatch_type"])
        model_only.append(rca.classify_root_cause(bid)["predicted_root_cause"])
        agent.append(case["rca"]["root_cause"])
        outcomes[case["status"]] += 1

    n = len(breaks)
    print(f"TEST breaks: {n}")
    print(f"root-cause macro-F1, model alone:          {f1_score(truth, model_only, average='macro'):.3f}")
    print(f"root-cause macro-F1, RCA agent (+notice):  {f1_score(truth, agent, average='macro'):.3f}")
    print(f"needed a person before anything ran:       {needed_person} ({needed_person / n:.0%})")
    print(f"ran straight through on policy:            {n - needed_person} ({(n - needed_person) / n:.0%})")
    print(f"outcomes: {dict(outcomes)}")
    print(f"unauthorised executions: {unauthorised}")


if __name__ == "__main__":
    main()
