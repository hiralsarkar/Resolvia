import streamlit as st
from theme import inject_global_css
import workbench
import realistic_case
import operational_views
import backend_bridge as bb

st.set_page_config(page_title="Resolvia", page_icon="◆", layout="wide", initial_sidebar_state="expanded")
inject_global_css()

if "nav" not in st.session_state:
    st.session_state["nav"] = "Home"
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

    operational_views.render_operator_context()
    st.markdown("<hr/>", unsafe_allow_html=True)

    pages = ["Home", "Operations Desk", "Case Investigation", "Resolution Control", "Resolution Playbook", "Audit Trail", "Manager Dashboard"]
    friendly = {
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
                bb.audit("CASE_AUDIT_OPENED", sb, "Operator opened the break audit from the active-case panel")
                st.rerun()
    else:
        st.caption("No break selected")

    st.markdown("<hr/>", unsafe_allow_html=True)
    st.caption("Human-led operations. Every decision and action is recorded.")

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
