"""
The break taxonomy: 4 families and 20 root causes.

Family (POSITION, CASH, SETTLEMENT, TRADE) is what the reconciliation engine
tags and what Triage routes on. Root cause is what RCA has to work out, and
it's the target of the main classifier. Family turned out to be too easy to
be an interesting model target (it is close to "which table has a
difference"); see check_ml_targets.py.

Corporate actions show up as POSITION breaks, because the position simply
looks wrong, and carry a corporate_action_type of MANDATORY or VOLUNTARY.
A mandatory event (a split, a bonus) is mechanical. A voluntary one (a
tender, a conversion) needs the client to choose. In the numbers the two look
the same, on purpose: telling them apart means reading the notice. Whatever
the model says, a person signs off on every corporate action.

Severity: P0 is settlement or critical risk, P1 high, P2 lower.
"""

ROOT_CAUSES = {
    # position
    "POS_MISSING_BOOKING": {
        "family": "POSITION", "severity": "P0",
        "description": "Missing booking: the position never showed up externally",
    },
    "POS_WRONG_QUANTITY": {
        "family": "POSITION", "severity": "P1",
        "description": "Wrong quantity: the external position is off by a non-round amount",
    },
    "POS_TIMING_DIFFERENCE": {
        "family": "POSITION", "severity": "P2",
        "description": "Timing difference: quantities agree but as-of dates don't (usually clears itself)",
    },
    "CA_INCORRECT_ENTITLEMENT": {
        "family": "POSITION", "severity": "P1",
        "description": "Corporate action entitlement calculated incorrectly (wrong ratio applied)",
    },
    "CA_MANDATORY_NOT_REFLECTED": {
        "family": "POSITION", "severity": "P1",
        "description": "Mandatory corporate action (split or bonus) not yet reflected externally",
    },
    "CA_VOLUNTARY_DECISION": {
        "family": "POSITION", "severity": "P1",
        "description": "Voluntary corporate action (tender or conversion) waiting on the client's election",
    },

    # cash
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
        "description": "Cash posted in another currency or at a stale or wrong FX rate",
    },

    # settlement
    "SETL_WRONG_SSI": {
        "family": "SETTLEMENT", "severity": "P0",
        "description": "Settlement instruction points at the wrong SSI or beneficiary account, so the payment fails",
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
        "description": "Settlement recorded against the wrong date (an off-by-one, like a holiday calendar slip)",
    },

    # trade and confirmation
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

# corporate_action_type written onto the breaks row; blank for everything else
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
