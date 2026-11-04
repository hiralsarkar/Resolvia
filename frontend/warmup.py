"""
Background warm-up, started once per server process after the first page
has been sent to the browser.

The Agent Architecture page needs nothing from the backend, so it renders
straight away. While the visitor watches it, this thread loads everything
the working pages need, lightest first: the app modules, the data tables,
the two classifiers, the vector indexes and finally the sentence-transformer
model (the one real download, roughly 90 MB on a cold start).

It lives in its own module, not in app.py, because Streamlit re-executes
app.py on every interaction; module state here survives reruns, so the work
happens exactly once.
"""

import threading

_lock = threading.Lock()
_started = False
status = {"done": False, "step": None, "errors": []}


def _step(name, fn):
    status["step"] = name
    try:
        fn()
    except Exception as e:  # warm-up must never break the app
        status["errors"].append(f"{name}: {type(e).__name__}: {e}"[:200])


def _run():
    def app_modules():
        import workbench  # noqa: F401  (pulls in backend_bridge, orchestrator, pandas, langgraph)
        import realistic_case  # noqa: F401

    def data():
        from investigation import _tables
        _tables()

    def classifiers():
        import triage, rca
        triage._model_bundle(); rca._model_bundle()
        triage._features_df(); rca._features_df()

    def indexes():
        from investigation import _index
        for name in ("evidence_index", "ca_reference_index", "resolved_cases_index"):
            _index(name)

    def embedding_model():
        from embed_store import get_model
        get_model()

    for name, fn in (("app modules", app_modules), ("data", data), ("classifiers", classifiers),
                     ("vector indexes", indexes), ("embedding model", embedding_model)):
        _step(name, fn)
    status["step"] = None
    status["done"] = True


def start():
    """Kick off the warm-up once per process; later calls return immediately."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_run, name="resolvia-warmup", daemon=True).start()
