import streamlit as st


def render():
    st.markdown("""
    <style>
    .arch-eyebrow{color:#4CE0FF;font-size:.72rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase}
    .arch-title{font-size:2.35rem;font-weight:850;letter-spacing:-.045em;margin:.2rem 0 .35rem;color:#F2F3F8}
    .arch-sub{color:#9BA2B5;font-size:1rem;max-width:850px;margin-bottom:1.4rem}
    .arch-wrap{background:linear-gradient(145deg,#11141D,#171B27);border:1px solid #2A3040;border-radius:18px;padding:22px;margin:12px 0 18px}
    .arch-node{background:#1B2130;border:1px solid #354056;border-radius:12px;padding:14px 12px;text-align:center;min-height:90px}
    .arch-node .num{font-size:.68rem;color:#4CE0FF;font-weight:800;letter-spacing:.1em}
    .arch-node .name{font-weight:800;font-size:1rem;color:#F2F3F8;margin:.35rem 0}
    .arch-node .desc{font-size:.76rem;color:#A5ADBF;line-height:1.35}
    .arch-arrow{text-align:center;color:#4CE0FF;font-size:1.35rem;font-weight:800;padding:3px 0}
    .arch-gate{background:#28251B;border:1px solid #8A7137;border-radius:12px;padding:14px;text-align:center}
    .arch-gate .name{font-weight:800;color:#F4D58B}
    .arch-gate .desc{font-size:.78rem;color:#D3C59F;margin-top:4px}
    .arch-note{color:#9BA2B5;font-size:.82rem;margin-top:8px}
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="arch-eyebrow">Resolvia · System Overview</div><div class="arch-title">Agent Architecture</div><div class="arch-sub">How an investment-banking trade break moves from intake through evidence-backed analysis, controlled resolution, and independent verification.</div>', unsafe_allow_html=True)

    st.markdown('<div class="arch-wrap">', unsafe_allow_html=True)
    cols = st.columns(3)
    nodes = [
        ("01", "Triage Agent", "Classifies the break, checks data quality, and sets priority and routing."),
        ("02", "Investigation Agent", "Collects structured records, supporting documents, and relevant precedent."),
        ("03", "Root-Cause Analysis", "Identifies the likely cause and explains the evidence and confidence."),
    ]
    for col, (num, name, desc) in zip(cols, nodes):
        with col:
            st.markdown(f'<div class="arch-node"><div class="num">STAGE {num}</div><div class="name">{name}</div><div class="desc">{desc}</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="arch-arrow">↓ &nbsp; Evidence and diagnosis feed the proposal</div>', unsafe_allow_html=True)
    st.markdown('<div class="arch-node"><div class="num">STAGE 04</div><div class="name">Resolution Proposal</div><div class="desc">Recommends an action and authority tier using the root cause, evidence, and resolution rules.</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="arch-arrow">↓</div>', unsafe_allow_html=True)
    st.markdown('<div class="arch-gate"><div class="name">Human Control Gate</div><div class="desc">Policy checks whether the proposed action is permitted. Where approval is required, the case pauses until an authorized human records a decision.</div></div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        st.markdown('<div class="arch-arrow">↙</div><div class="arch-node"><div class="name">Controlled Action</div><div class="desc">Approved actions follow the controlled execution path. Manual actions are performed by the analyst in the relevant operational system and recorded separately.</div></div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="arch-arrow">↘</div><div class="arch-node"><div class="name">Blocked / Escalated</div><div class="desc">If approval is denied or the case needs another owner, it remains open for review; no unauthorized correction is executed.</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="arch-arrow">↓</div><div class="arch-node"><div class="num">FINAL CONTROL</div><div class="name">Validation & Audit</div><div class="desc">Checks the post-action outcome or independently verifies a recorded manual correction. The case closes only after verification; unresolved cases remain open or reopen.</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="arch-note">Design principle: AI supports investigation and recommendations; humans retain authority over controlled decisions. Every material step is recorded against the break.</div>', unsafe_allow_html=True)

    a, b, c = st.columns(3)
    with a:
        st.markdown("**Analyst**  \nWork the break, review evidence, and follow the resolution guide.")
        if st.button("Open Break Queue →", type="primary", use_container_width=True, key="arch_queue"):
            st.session_state["nav"] = "Operations Desk"; st.rerun()
    with b:
        st.markdown("**Manager**  \nReview workload, ageing, exposure, and escalations.")
        if st.button("Open Manager Overview →", use_container_width=True, key="arch_manager"):
            st.session_state["nav"] = "Manager Dashboard"; st.rerun()
    with c:
        st.markdown("**Auditor**  \nTrace actions and decisions through the case audit trail.")
        if st.button("Open Audit Trail →", use_container_width=True, key="arch_audit"):
            st.session_state["nav"] = "Audit Trail"; st.rerun()
