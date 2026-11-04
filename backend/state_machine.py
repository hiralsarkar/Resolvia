"""Allowed case transitions for human-controlled workflow paths."""

TRANSITIONS = {
    "CASE_CREATED": {"IN_REVIEW", "ESCALATED"},
    "IN_REVIEW": {"AWAITING_APPROVAL", "MANUAL_IN_PROGRESS", "ESCALATED"},
    "AWAITING_APPROVAL": {"CLOSED", "REJECTED", "ESCALATED"},
    "MANUAL_IN_PROGRESS": {"AWAITING_VERIFICATION", "ESCALATED"},
    "AWAITING_VERIFICATION": {"CLOSED", "REOPENED", "ESCALATED"},
    "REOPENED": {"MANUAL_IN_PROGRESS", "AWAITING_APPROVAL", "ESCALATED"},
    "ON_HOLD": {"IN_REVIEW", "ESCALATED"},
    "ESCALATED": {"IN_REVIEW", "AWAITING_APPROVAL", "MANUAL_IN_PROGRESS", "CLOSED"},
    "CLOSED": set(),
    "REJECTED": set(),
}


def require_transition(current, target):
    if current == target:
        return
    if target not in TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid case transition: {current} -> {target}")
