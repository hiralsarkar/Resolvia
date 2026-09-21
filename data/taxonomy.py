"""
taxonomy.py

The Resolvia break taxonomy (v7 plan, Section 6 + Section 10): 4 break
families for routing, 20 root causes for the actual investigation/ML
target. See check_ml_targets.py - the 4 families
are deliberately too coarse to be a meaningful ML target on their own
(family is close to "which table has a non-null delta"); root_cause is
the harder, more realistic classification problem and is what Week 2's
model comparison should predict.

Corporate action handling (v7 Section 7/27): CA breaks manifest as
POSITION-family breaks (the position simply looks wrong), but carry a
separate `corporate_action_type` of MANDATORY or VOLUNTARY. Mandatory
is mechanical (mirrors a clean, known ratio like a 2-for-1 split).
Voluntary looks the same at the structured-data level - deliberately,
since telling them apart is supposed to require reading the corporate
action notice (Week 2+ document evidence), not just fitting numbers.
Whichever agent handles this later must hardcode "voluntary always
escalates to a human regardless of confidence" - that rule is a
governance choice, not something to learn from data.
"""

# ---------------------------------------------------------------------
# Root cause catalogue: (root_cause_key, family, severity, description)
# family in {POSITION, CASH, SETTLEMENT, TRADE}
# severity: P0 (settlement/critical risk), P1 (high), P2 (lower)
# ---------------------------------------------------------------------

ROOT_CAUSES = {
    # --- POSITION family ---
    "POS_MISSING_BOOKING": {
        "family": "POSITION", "severity": "P0",
        "description": "Missing upstream booking - position never reflected externally",
    },
    "POS_WRONG_QUANTITY": {
        "family": "POSITION", "severity": "P1",
        "description": "Wrong quantity - external position differs by a non-round amount",
    },
    "POS_TIMING_DIFFERENCE": {
        "family": "POSITION", "severity": "P2",
        "description": "Timing difference - quantities agree, as-of dates don't (expected to self-resolve)",
    },
    "CA_INCORRECT_ENTITLEMENT": {
        "family": "POSITION", "severity": "P1",
        "description": "Corporate action entitlement calculated incorrectly (wrong ratio applied)",
    },
    "CA_MANDATORY_NOT_REFLECTED": {
        "family": "POSITION", "severity": "P1",
        "description": "Mandatory corporate action (split/bonus) not yet reflected externally - mechanical, auto-correctable",
    },
    "CA_VOLUNTARY_DECISION": {
        "family": "POSITION", "severity": "P1",
        "description": "Voluntary corporate action (tender/conversion) pending an election - requires a human business decision, always escalated",
    },

    # --- CASH family ---
    "CASH_MISSING_ENTRY": {
        "family": "CASH", "severity": "P0",
        "description": "Expected cash movement never posted",
    },
    "CASH_DUPLICATE_ENTRY": {
        "family": "CASH", "severity": "P1",
        "description": "Same cash movement posted twice",
    },
    "CASH_WRONG_AMOUNT": {
        "family": "CASH", "severity": "P1",
        "description": "Cash amount posted differs from expected trade value by a non-round amount",
    },
    "CASH_FX_INPUT_DIFFERENCE": {
        "family": "CASH", "severity": "P2",
        "description": "Cash posted in a different currency / at a stale or incorrect FX rate",
    },

    # --- SETTLEMENT family ---
    "SETL_WRONG_SSI": {
        "family": "SETTLEMENT", "severity": "P0",
        "description": "Settlement instruction references the wrong SSI/beneficiary account - the payment-failure flagship scenario",
    },
    "SETL_LATE_COUNTERPARTY": {
        "family": "SETTLEMENT", "severity": "P1",
        "description": "Counterparty has not settled by the expected date",
    },
    "SETL_MISSING_INSTRUCTION": {
        "family": "SETTLEMENT", "severity": "P0",
        "description": "No settlement instruction was ever issued",
    },
    "SETL_INCORRECT_DATE": {
        "family": "SETTLEMENT", "severity": "P2",
        "description": "Settlement recorded against the wrong date (holiday-calendar-style off-by-one)",
    },

    # --- TRADE / CONFIRMATION family ---
    "TRADE_PRICE_MISMATCH": {
        "family": "TRADE", "severity": "P2",
        "description": "Confirmed price differs from booked price",
    },
    "TRADE_QUANTITY_MISMATCH": {
        "family": "TRADE", "severity": "P1",
        "description": "Confirmed quantity differs from booked quantity",
    },
    "TRADE_DATE_MISMATCH": {
        "family": "TRADE", "severity": "P2",
        "description": "Confirmed trade date differs from booked trade date",
    },
    "TRADE_COUNTERPARTY_ID_MISMATCH": {
        "family": "TRADE", "severity": "P1",
        "description": "Confirmed counterparty identifier differs from booked counterparty",
    },
    "CONF_MISSING": {
        "family": "TRADE", "severity": "P0",
        "description": "External confirmation never received",
    },
    "CONF_DISAGREEMENT": {
        "family": "TRADE", "severity": "P1",
        "description": "External confirmation received but disagrees with the booking on multiple fields",
    },
}

BREAK_FAMILIES = ["POSITION", "CASH", "SETTLEMENT", "TRADE"]

CA_ROOT_CAUSES = {"CA_INCORRECT_ENTITLEMENT", "CA_MANDATORY_NOT_REFLECTED", "CA_VOLUNTARY_DECISION"}

# root cause -> corporate_action_type written onto the breaks row (None for
# every non-CA root cause). Only CA_VOLUNTARY_DECISION carries the hardcoded
# always-escalate rule downstream.
CORPORATE_ACTION_TYPE = {
    "CA_INCORRECT_ENTITLEMENT": "MANDATORY",
    "CA_MANDATORY_NOT_REFLECTED": "MANDATORY",
    "CA_VOLUNTARY_DECISION": "VOLUNTARY",
}


def root_causes_for_family(family):
    return [k for k, v in ROOT_CAUSES.items() if v["family"] == family]


def validate_taxonomy():
    assert set(BREAK_FAMILIES) == {v["family"] for v in ROOT_CAUSES.values()}
    for family in BREAK_FAMILIES:
        assert root_causes_for_family(family), f"family {family} has no root causes"
    for k in CA_ROOT_CAUSES:
        assert k in ROOT_CAUSES
    return True


if __name__ == "__main__":
    validate_taxonomy()
    print(f"{len(ROOT_CAUSES)} root causes across {len(BREAK_FAMILIES)} families:")
    for family in BREAK_FAMILIES:
        causes = root_causes_for_family(family)
        print(f"  {family} ({len(causes)}): {', '.join(causes)}")
