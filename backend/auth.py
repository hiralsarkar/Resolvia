"""Identity and role checks for state-changing operations.

The demo roster is deliberately small; production should replace it with SSO
or signed tokens.  The backend still owns the check so a UI cannot impersonate
an approver or verifier by editing a text field.
"""
import os

DEFAULT_ROSTER = {"OPS-1047": "analyst", "OPS-LEAD": "approver", "OPS-VERIFY": "verifier"}


def roster():
    raw = os.getenv("RESOLVIA_ROSTER")
    if not raw:
        return dict(DEFAULT_ROSTER)
    parsed = {}
    for item in raw.split(","):
        if ":" in item:
            ident, role = item.split(":", 1)
            parsed[ident.strip().upper()] = role.strip().lower()
    return parsed or dict(DEFAULT_ROSTER)


def require_actor(actor_id, roles=()):
    actor = (actor_id or "").strip().upper()
    role = roster().get(actor)
    if role is None:
        raise PermissionError("unknown operator identity")
    if roles and role not in roles:
        raise PermissionError(f"operator role {role!r} cannot perform this action")
    return {"actor_id": actor, "role": role}


def require_distinct(actor_id, other_id, label="actor"):
    if actor_id.strip().upper() == other_id.strip().upper():
        raise PermissionError(f"maker-checker violation: verifier must differ from {label}")
