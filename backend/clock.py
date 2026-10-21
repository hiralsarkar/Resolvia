"""Single source of "now" for every audit timestamp in the backend.

Normal runs use the wall clock (UTC). The seeding script swaps in a
scripted clock so the historical cases it creates carry realistic,
back-dated timestamps (the business day the break arrived, plus the
hours it took to work) instead of all sharing the second the seed ran.
"""

from datetime import datetime, timezone

_SOURCE = None  # optional zero-arg callable returning an aware datetime


def now():
    return _SOURCE() if _SOURCE else datetime.now(timezone.utc)


def now_iso():
    return now().astimezone(timezone.utc).isoformat(timespec="seconds")


def set_source(fn):
    """Install a custom clock (seeding only). Pass None to restore the wall clock."""
    global _SOURCE
    _SOURCE = fn
