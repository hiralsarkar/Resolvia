"""
Background warm-up, started once per server process after the first page
has been sent to the browser.

The Agent Architecture page needs nothing from the backend, so it renders
straight away. While the visitor watches it, this thread loads everything
the working pages need, lightest first: the app modules, the data tables,
the vector indexes, the triage classifier and the shared features. The two
memory-heavy models (RCA and sentence-transformer) still load on first use.

It lives in its own module, not in app.py, because Streamlit re-executes
app.py on every interaction; module state here survives reruns, so the work
happens exactly once.
"""

import threading
import time

_lock = threading.Lock()
_started = False
status = {"done": False, "step": None, "errors": [], "timings": {}}

# Streamlit runs scripts on worker threads that share one Python interpreter,
# so CPU-heavy loading here would slow down whatever page is rendering. The
# heavy steps therefore only run while no page is being drawn.
_last_start = 0.0
_last_end = 0.0


def page_started():
    global _last_start
    _last_start = time.time()


def page_finished():
    global _last_end
    _last_end = time.time()


def _wait_until_idle(quiet=2.0):
    while True:
        now = time.time()
        rendering = _last_start > _last_end and now - _last_start < 20  # 20s guards a run that never finished
        if not rendering and now - max(_last_end, _last_start) >= quiet:
            return
        time.sleep(0.5)


def _step(name, fn, heavy=False):
    if heavy:
        _wait_until_idle()
    status["step"] = name
    t = time.time()
    try:
        fn()
    except Exception as e:  # warm-up must never break the app
        status["errors"].append(f"{name}: {type(e).__name__}: {e}"[:200])
    status["timings"][name] = round(time.time() - t, 2)
    print(f"[resolvia-warmup] {name}: {status['timings'][name]}s", flush=True)


def _run():
    def app_modules():
        import workbench  # noqa: F401  (pulls in backend_bridge, orchestrator, pandas, langgraph)
        import realistic_case  # noqa: F401

    def data():
        from investigation import _tables
        _tables()

    def triage_model():
        import triage
        triage._model_bundle()

    def features():
        import triage, rca
        triage._features_df(); rca._features_df()

    def indexes():
        from investigation import _index
        for name in ("evidence_index", "ca_reference_index", "resolved_cases_index"):
            _index(name)

    # Light first, then the heavy ones one at a time, each waiting for a quiet moment.
    # The RCA model (~650 MB in memory) and the sentence-transformer model (~400 MB
    # with torch) are deliberately NOT preloaded: together they push the server past
    # Streamlit Cloud's memory limit, which crashes the app. They load on first use.
    for name, fn, heavy in (("app modules", app_modules, False), ("data", data, False),
                            ("vector indexes", indexes, False), ("triage model", triage_model, True),
                            ("features", features, True)):
        _step(name, fn, heavy)
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
