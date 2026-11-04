import streamlit as st
from theme import inject_global_css

st.set_page_config(page_title="Resolvia", page_icon="◆", layout="wide", initial_sidebar_state="expanded")
inject_global_css()

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

    st.sidebar.caption("OPERATOR ID")
    value = st.sidebar.text_input("", value=st.session_state.get("operator_id", "OPS-1047"), key="operator_id_input", label_visibility="collapsed").strip().upper() or "OPS-1047"
    st.session_state["operator_id"] = value
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
    import command_center
    command_center.render()
elif nav in ("Home", "Operations Desk", "Audit Trail", "Manager Dashboard"):
    import workbench
    if nav == "Home":
        workbench.render_home()
    elif nav == "Operations Desk":
        workbench.render_operations()
    elif nav == "Audit Trail":
        workbench.render_audit()
    else:
        workbench.render_manager()
elif nav in ("Case Investigation", "Resolution Control", "Resolution Playbook"):
    import realistic_case
    if nav == "Case Investigation":
        realistic_case.render_case()
    elif nav == "Resolution Control":
        realistic_case.render_resolution()
    else:
        realistic_case.render_guide()
