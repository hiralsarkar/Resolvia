import streamlit as st
from theme import inject_global_css
import command_center

# The Agent Architecture page needs nothing from the backend, so the heavy
# modules (agents, LangGraph, models, data) are imported only when a page
# needs them. That lets the landing page draw before any of them load.

st.set_page_config(page_title="Resolvia", page_icon="◆", layout="wide", initial_sidebar_state="expanded")
inject_global_css()


def _start_demo_day():
    """Starts the replayed working day (once per process). backend_bridge
    goes first because it puts the backend on sys.path."""
    import backend_bridge  # noqa: F401
    import demo_history
    demo_history.start()

if "nav" not in st.session_state:
    st.session_state["nav"] = "Agent Architecture"
if "selected_break" not in st.session_state:
    st.session_state["selected_break"] = None
if "operator_id" not in st.session_state:
    st.session_state["operator_id"] = "OPS-1047"

with st.sidebar:
    if st.button("Resolvia.", key="home_brand_btn"):
        st.session_state["nav"] = "Home"
        st.rerun()
    st.markdown('<div class="resolvia-tagline">From Break to Verified Resolution</div>', unsafe_allow_html=True)
    st.markdown("<br/>", unsafe_allow_html=True)

    # same as operational_views.render_operator_context(), without importing
    # the backend unless the operator ID actually changes
    st.sidebar.caption("OPERATOR ID")
    value = st.sidebar.text_input("", value=st.session_state.get("operator_id", "OPS-1047"), key="operator_id_input", label_visibility="collapsed").strip().upper() or "OPS-1047"
    if value != st.session_state.get("operator_id"):
        st.session_state["operator_id"] = value
        import backend_bridge as bb
        bb.audit("OPERATOR_SESSION", detail=f"Operator context set to {value}")
    st.sidebar.caption(f"Signed in as **{value}**")
    st.markdown("<hr/>", unsafe_allow_html=True)

    pages = ["Agent Architecture", "Home", "Operations Desk", "Case Investigation", "Resolution Control", "Resolution Playbook", "Audit Trail", "Manager Dashboard"]
    friendly = {
        "Agent Architecture": "Agent Architecture",
        "Home": "Home",
        "Operations Desk": "Break Queue",
        "Case Investigation": "Case Workspace",
        "Resolution Control": "Resolution",
        "Resolution Playbook": "Manual Guide",
        "Audit Trail": "Audit Trail",
        "Manager Dashboard": "Manager Overview",
    }
    nav = st.radio("Navigate", pages, index=pages.index(st.session_state["nav"]), format_func=lambda p: friendly[p], label_visibility="collapsed")
    st.session_state["nav"] = nav

    st.markdown("<hr/>", unsafe_allow_html=True)
    sb = st.session_state.get("selected_break")
    if sb:
        st.caption("ACTIVE BREAK")
        st.markdown(f'<span class="mono" style="color:#4CE0FF; font-size:1.25rem; font-weight:700;">{sb}</span>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Open case", key="sidebar_case", use_container_width=True):
                st.session_state["nav"] = "Case Investigation"
                st.rerun()
        with c2:
            if st.button("Audit", key="sidebar_audit", use_container_width=True):
                st.session_state["audit_break_filter"] = sb
                st.session_state["nav"] = "Audit Trail"
                import backend_bridge as bb
                bb.audit("CASE_AUDIT_OPENED", sb, "Operator opened the break audit from the active-case panel")
                st.rerun()
    else:
        st.caption("No break selected")

    st.markdown("<hr/>", unsafe_allow_html=True)
    st.caption("Human-led operations. Every decision and action is recorded.")

if nav == "Agent Architecture":
    command_center.render()
    _start_demo_day()  # after the page has been sent, so it doesn't delay it
else:
    _start_demo_day()
    import workbench
    import realistic_case
    if nav == "Home":
        workbench.render_home()
    elif nav == "Operations Desk":
        workbench.render_operations()
    elif nav == "Case Investigation":
        realistic_case.render_case()
    elif nav == "Resolution Control":
        realistic_case.render_resolution()
    elif nav == "Resolution Playbook":
        realistic_case.render_guide()
    elif nav == "Audit Trail":
        workbench.render_audit()
    elif nav == "Manager Dashboard":
        workbench.render_manager()
