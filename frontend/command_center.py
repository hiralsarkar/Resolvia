"""
command_center.py - the app's home page.

Embeds the same command-center animation published as the marketing
hero artifact (frontend/assets/command_center.html - single source of
truth, edit that file and both the artifact and this page pick it up)
so clicking into the actual product opens the identical experience,
not a lookalike. Pure presentation - no backend calls, no case state.

The "Start Reviewing Exceptions" button below is a real Streamlit
button, not part of the embedded HTML - st.components.v1.html renders
in a sandboxed iframe that can't call back into Streamlit's session
state, so the one actual navigation action on this page has to live
outside it. This is also the app's single most important guided-next-
step control: a first-time, non-technical user should never have to
work out the sidebar on their own to get from "watching the demo" to
"looking at a real exception."
"""

import os
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(HERE, "assets", "command_center.html")


def render():
    c1, c2, c3 = st.columns([1, 1.3, 1])
    with c2:
        if st.button("Start Reviewing Exceptions  →", key="cc_open_ops", type="primary"):
            st.session_state["nav"] = "Operations Desk"
            st.rerun()
    with open(HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    st.components.v1.html(html, height=1400, scrolling=False)
