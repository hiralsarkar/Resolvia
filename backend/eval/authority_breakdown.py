"""
How many proposals need a person's approval, and how much money sits behind them.

Runs the Resolution Proposal agent over every break and counts the authority
tiers. These are the numbers behind "share of actions needing approval" and
"straight-through rate".
"""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents"))
from resolution import propose
from investigation import _tables


def main():
    breaks = _tables()["breaks"]
    tiers = Counter()
    flagged = needs_approval = 0
    exposure_needing_approval = 0.0

    for bid in breaks:
        p = propose(bid)
        tiers[p["authority_tier"]] += 1
        flagged += p["rca_flagged_for_human_review"]
        if p["approval_required"]:
            needs_approval += 1
            exposure_needing_approval += p["risk"]["financial_exposure"]

    n = len(breaks)
    print(f"Breaks: {n}")
    for tier, count in tiers.items():
        print(f"  {tier}: {count} ({count / n:.1%})")
    print(f"Diagnosis flagged for a person (corporate action or low confidence): {flagged} ({flagged / n:.1%})")
    print(f"Needs approval before anything runs: {needs_approval} ({needs_approval / n:.1%})")
    print(f"Straight through on policy: {n - needs_approval} ({(n - needs_approval) / n:.1%})")
    print(f"Exposure behind proposals that need approval: INR {exposure_needing_approval:,.0f}")


if __name__ == "__main__":
    main()
