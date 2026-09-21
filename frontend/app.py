"""
app.py - Resolvia operational prototype. Run with:
  streamlit run frontend/app.py
"""

import streamlit as st

from theme import inject_global_css
import command_center
import views

st.set_page_config(page_title="Resolvia", page_icon="◆", layout="wide",
                    initial_sidebar_state="expanded")
inject_global_css()

if "nav" not in st.session_state:
    st.session_state["nav"] = "Command Center"
if "selected_break" not in st.session_state:
    st.session_state["selected_break"] = None

with st.sidebar:
    if st.button("Resolvia.", key="home_brand_btn"):
        st.session_state["nav"] = "Command Center"
        st.rerun()
    st.markdown('<div class="resolvia-tagline">From Break to Verified Resolution</div>',
                unsafe_allow_html=True)
    st.markdown("<br/>", unsafe_allow_html=True)

    pages = ["Command Center", "Operations Desk", "Case Investigation", "Resolution Control", "Analytics"]
    friendly = {"Command Center": "Home", "Operations Desk": "1 · Choose an exception",
                "Case Investigation": "2 · Watch the analysis", "Resolution Control": "3 · Make the decision",
                "Analytics": "Overall results"}
    nav = st.radio("Navigate", pages, index=pages.index(st.session_state["nav"]),
                    format_func=lambda p: friendly[p], label_visibility="collapsed")
    st.session_state["nav"] = nav

    st.markdown("<hr/>", unsafe_allow_html=True)
    sb = st.session_state.get("selected_break")
    if sb:
        st.caption("ACTIVE CASE")
        st.markdown(f'<span class="mono" style="color:#4CE0FF; font-size:1.4rem; font-weight:700;">{sb}</span>',
                    unsafe_allow_html=True)
    else:
        st.caption("No case selected")

    st.markdown("<hr/>", unsafe_allow_html=True)
    st.caption("AI investigates. Humans authorize.\nSystems execute. AI validates.")

# Always render this slot (same position on every page) so Streamlit never recycles
# another element's DOM node into it; it only carries a script when the page changed.
_scroll = ""
if st.session_state.get("_last_nav") != nav:
    st.session_state["_last_nav"] = nav
    _scroll = ("<script>var m=window.parent.document.querySelector('[data-testid=\"stMain\"]');"
               "if(m){m.scrollTo(0,0);}window.parent.scrollTo(0,0);</script>")
st.components.v1.html("<!-- -->" + _scroll, height=0)

if nav == "Command Center":
    command_center.render()
elif nav == "Operations Desk":
    views.render_operations_desk()
elif nav == "Case Investigation":
    views.render_case_investigation()
elif nav == "Resolution Control":
    views.render_resolution_control()
elif nav == "Analytics":
    views.render_analytics()
