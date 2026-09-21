"""
authority_breakdown.py

Runs the Resolution Proposal Agent across every break and reports the
authority-tier / approval-required distribution - the concrete number
behind the "% actions requiring human approval" and "straight-
through investigation rate" KPIs.
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
    rca_escalations = 0
    total_exposure_controlled = 0.0

    for bid in breaks:
        p = propose(bid)
        tiers[p["authority_tier"]] += 1
        if p["rca_flagged_for_human_review"]:
            rca_escalations += 1
        if p["authority_tier"] == "CONTROLLED_ACTION":
            total_exposure_controlled += p["risk"]["financial_exposure"]

    n = len(breaks)
    print(f"Total breaks: {n}")
    for tier, count in tiers.items():
        print(f"  {tier}: {count} ({count/n:.1%})")
    print(f"\nRCA-flagged for human diagnostic review (CA or low confidence): "
          f"{rca_escalations} ({rca_escalations/n:.1%})")
    print(f"Straight-through investigation rate (neither RCA-escalated nor "
          f"CONTROLLED_ACTION): {n - max(tiers['CONTROLLED_ACTION'], rca_escalations)} approx - "
          f"see note below")
    print(f"\nTotal financial exposure behind CONTROLLED_ACTION proposals: "
          f"INR {total_exposure_controlled:,.0f}")
    print("\nNote: 'straight-through investigation rate' isn't a clean single number from "
          "these two flags alone (they can overlap or not) - report both rates above "
          "separately in the final deliverable rather than collapsing them into one figure.")


if __name__ == "__main__":
    main()
