"""
The landing page: the agent-architecture animation from
assets/command_center.html, followed by a real button into the work queue.

The button has to live outside the animation because Streamlit renders HTML
components in a sandboxed iframe that can't change the app's page. It's the
one thing a first-time visitor needs to find, so it sits right under the
animation.
"""

import os
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(HERE, "assets", "command_center.html")


def render():
    with open(HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    st.components.v1.html(html, height=1560, scrolling=False)

    # the way in sits after the animation, not above it
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.3, 1])
    with c2:
        if st.button("Start Reviewing Exceptions  →", key="cc_open_ops", type="primary", use_container_width=True):
            st.session_state["nav"] = "Operations Desk"
            st.rerun()
