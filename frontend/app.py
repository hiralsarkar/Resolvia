import streamlit as st
from theme import inject_global_css
import command_center
import views
import operational_views
import backend_bridge as bb

st.set_page_config(page_title="Resolvia", page_icon="◆", layout="wide", initial_sidebar_state="expanded")
inject_global_css()
if "nav" not in st.session_state: st.session_state["nav"]="Command Center"
if "selected_break" not in st.session_state: st.session_state["selected_break"]=None
if "operator_id" not in st.session_state: st.session_state["operator_id"]="OPS-1047"

with st.sidebar:
    if st.button("Resolvia.",key="home_brand_btn"): st.session_state["nav"]="Command Center"; st.rerun()
    st.markdown('<div class="resolvia-tagline">From Break to Verified Resolution</div>',unsafe_allow_html=True); st.markdown("<br/>",unsafe_allow_html=True)
    operational_views.render_operator_context(); st.markdown("<hr/>",unsafe_allow_html=True)
    pages=["Command Center","Operations Desk","Case Investigation","Resolution Control","Resolution Playbook","Audit Trail","Manager Dashboard","Analytics"]
    friendly={"Command Center":"Home","Operations Desk":"1 · Choose an exception","Case Investigation":"2 · Investigate","Resolution Control":"3 · Make the decision","Resolution Playbook":"4 · Resolve manually","Audit Trail":"Audit Trail","Manager Dashboard":"5 · Manager view","Analytics":"Model & portfolio analytics"}
    nav=st.radio("Navigate",pages,index=pages.index(st.session_state["nav"]),format_func=lambda p:friendly[p],label_visibility="collapsed"); st.session_state["nav"]=nav
    st.markdown("<hr/>",unsafe_allow_html=True)
    sb=st.session_state.get("selected_break")
    if sb:
        st.caption("ACTIVE CASE"); st.markdown(f'<span class="mono" style="color:#4CE0FF; font-size:1.4rem; font-weight:700;">{sb}</span>',unsafe_allow_html=True)
        if st.button("Open Audit Trail",key="sidebar_open_audit"): bb.audit("OPENED_CASE_AUDIT",sb,"Opened the case audit view from the sidebar"); st.session_state["nav"]="Audit Trail"; st.rerun()
    else: st.caption("No case selected")
    st.markdown("<hr/>",unsafe_allow_html=True); st.caption("Controlled workflow. Human approval remains the decision point.")

_scroll=""
if st.session_state.get("_last_nav")!=nav:
    st.session_state["_last_nav"]=nav; bb.audit("NAVIGATED",detail=f"Opened {nav}"); _scroll="<script>var m=window.parent.document.querySelector('[data-testid=\"stMain\"]');if(m){m.scrollTo(0,0);}window.parent.scrollTo(0,0);</script>"
st.components.v1.html("<!-- -->"+_scroll,height=0)

if nav=="Command Center": command_center.render()
elif nav=="Operations Desk": views.render_operations_desk()
elif nav=="Case Investigation": views.render_case_investigation()
elif nav=="Resolution Control": views.render_resolution_control()
elif nav=="Resolution Playbook": operational_views.render_resolution_playbook()
elif nav=="Audit Trail": operational_views.render_audit_trail()
elif nav=="Manager Dashboard": operational_views.render_manager_dashboard()
elif nav=="Analytics": views.render_analytics()

selected=st.session_state.get("selected_break")
if selected and selected!=st.session_state.get("_audited_selected_break"):
    bb.audit("BREAK_OPENED",selected,"Operator selected/opened break from the Operations Desk")
    st.session_state["_audited_selected_break"]=selected
