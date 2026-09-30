import streamlit as st
import pandas as pd
import backend_bridge as bb
from theme import COLORS, STATUS_LABEL, SEVERITY_LABEL

PLAYBOOKS = {
    "SETL_WRONG_SSI": ("Settlements Operations", "Settlements Manager", "Confirm the verified settlement instruction before amendment.", ["Verified SSI master record", "Custodian/counterparty confirmation", "Settlement date and account details"], ["Compare booked SSI with the verified SSI master.", "Contact Settlements Operations / Custodian Management.", "Record the confirmation reference and effective date.", "Amend the settlement instruction only after verification.", "Re-submit and verify settlement status."], ["Do not change SSI without verification.", "Do not close the break immediately after amendment."]),
    "SETL_LATE_COUNTERPARTY": ("Settlements Operations", "Settlements Manager", "Confirm counterparty settlement status and expected settlement timing.", ["Settlement record", "Counterparty/custodian status", "Settlement date and exception reason"], ["Confirm the contractual settlement date.", "Check current settlement status.", "Contact the counterparty/custodian for status and expected settlement time.", "Record the response and escalate if the SLA is breached.", "Re-check settlement status before closure."], ["Do not mark resolved based only on a verbal update."]),
    "CASH_WRONG_AMOUNT": ("Cash Operations", "Cash Operations Manager", "Reconcile the posted amount against the expected cash movement.", ["Cash ledger entry", "Expected trade value", "Bank/custodian confirmation"], ["Compare posted and expected amounts.", "Check currency and value date.", "Contact Cash Operations for the posting source.", "Correct the posting through the approved process.", "Verify the ledger balance after correction."], ["Do not manually overwrite a ledger value without an approved correction process."]),
    "TRADE_PRICE_MISMATCH": ("Trade Support / Middle Office", "Trade Support Manager", "Confirm the economically correct trade price and source of truth.", ["Trade confirmation", "Booking record", "Counterparty confirmation"], ["Compare booked price with external confirmation.", "Check whether fees, FX or corporate-action adjustments explain the difference.", "Contact Trade Support / Counterparty as appropriate.", "Record the confirmed price and correction reference.", "Reconcile the downstream records."], ["Do not overwrite trade economics without confirmation."]),
}
DEFAULT_PLAYBOOK = ("Operations / Middle Office", "Operations Manager", "Confirm the source-of-truth record and the approved resolution path.", ["Source record", "Comparison record", "Relevant confirmation or supporting document"], ["Review the structured evidence and identify the mismatching field.", "Contact the owning operations team shown above.", "Confirm the source-of-truth value and obtain supporting evidence.", "Perform the approved correction manually or through the controlled path.", "Reconcile the result and submit for validation."], ["Do not close the break without evidence of resolution.", "Do not bypass an approval requirement."])

def render_operator_context():
    st.sidebar.caption("OPERATOR ID")
    value = st.sidebar.text_input("", value=st.session_state.get("operator_id", "OPS-1047"), key="operator_id_input", label_visibility="collapsed").strip().upper() or "OPS-1047"
    if value != st.session_state.get("operator_id"):
        st.session_state["operator_id"] = value
        bb.audit("OPERATOR_SESSION", detail=f"Operator context set to {value}")
    st.sidebar.caption(f"Signed in as **{value}**")

def _playbook(case):
    return PLAYBOOKS.get(case.get("rca", {}).get("root_cause", ""), DEFAULT_PLAYBOOK)

def render_resolution_playbook():
    st.markdown('<span class="eyebrow">Resolution Guidance</span>', unsafe_allow_html=True); st.markdown("## Manual Resolution Playbook")
    st.caption("A controlled checklist for analysts when the fix is carried out manually.")
    bid=st.session_state.get("selected_break")
    if not bid: st.info("Select a break first."); return
    case=bb.get_case(bid)
    if not case: st.info("Run the case analysis first so the playbook can use the identified root cause."); return
    bb.audit("OPENED_RESOLUTION_PLAYBOOK",bid,"Analyst opened the manual resolution guide",dedupe_key=f"playbook:{bid}:{st.session_state.get('_nav_cycle',0)}")
    owner,escalation,reason,evidence,steps,do_not=_playbook(case); row=bb.load_breaks_df().set_index("break_id").loc[bid]
    st.markdown(f"### {bid}"); c1,c2,c3=st.columns(3); c1.metric("Owner",owner); c2.metric("Escalation",escalation); c3.metric("Severity",SEVERITY_LABEL.get(row.severity,row.severity))
    st.markdown("### Who to contact"); st.info(reason); st.markdown(f"**Primary:** {owner}  \n**Escalate to:** {escalation}")
    st.markdown("### What to do")
    for i,step in enumerate(steps,1): st.markdown(f"**{i}.** {step}")
    st.markdown("### Evidence to collect")
    for item in evidence: st.checkbox(item,key=f"pb_{bid}_{item}")
    st.markdown("### Before closing")
    for item in do_not: st.warning(item)
    st.caption("The final state should be validated after the manual correction. This guide does not bypass the human control gate.")

def render_audit_trail():
    st.markdown('<span class="eyebrow">Governance</span>',unsafe_allow_html=True); st.markdown("## Audit Trail"); st.caption("Human actions and system events recorded with Operations ID and UTC timestamp.")
    s=bb.audit_summary(); c1,c2,c3,c4,c5=st.columns(5); c1.metric("Events",s["total"]); c2.metric("Human actions",s["human"]); c3.metric("System events",s["system"]); c4.metric("Approvals",s["approvals"]); c5.metric("Escalations",s["escalations"])
    df=pd.DataFrame(bb.audit_events(limit=1000))
    if df.empty: st.info("No audit events recorded yet."); return
    df["timestamp"]=pd.to_datetime(df["timestamp"],utc=True); f1,f2,f3=st.columns(3); actors=f1.multiselect("Operator",sorted(df.actor_id.dropna().unique())); actions=f2.multiselect("Action",sorted(df.action.dropna().unique())); breaks=f3.multiselect("Break",sorted([x for x in df.break_id.dropna().unique() if x]));
    if actors: df=df[df.actor_id.isin(actors)]
    if actions: df=df[df.action.isin(actions)]
    if breaks: df=df[df.break_id.isin(breaks)]
    df["Timestamp"]=df.timestamp.dt.strftime("%Y-%m-%d %H:%M:%S UTC"); df=df.rename(columns={"actor_id":"Operations ID","action":"Action","break_id":"Break ID","detail":"What was done","source":"Source"}); st.dataframe(df[["Timestamp","Operations ID","Break ID","Action","What was done","Source"]],hide_index=True,width="stretch",height=520)

def render_manager_dashboard():
    import plotly.graph_objects as go
    st.markdown('<span class="eyebrow">Operations Command Center</span>',unsafe_allow_html=True); st.markdown("## Manager Dashboard"); st.caption("Operational snapshot of exception volume, ageing, exposure and work requiring attention.")
    df=bb.load_breaks_df().copy(); statuses=bb.all_case_statuses(); df["status"]=df.break_id.map(lambda b:statuses.get(b,"OPEN")); max_date=pd.to_datetime(df.business_date).max(); df["age_days"]=(max_date-pd.to_datetime(df.business_date)).dt.days.clip(lower=0); df["age_bucket"]=pd.cut(df.age_days,bins=[-1,0,1,2,3,10**6],labels=["0 days","1 day","2 days","3 days","4+ days"])
    resolved=df.status.eq("CLOSED").sum(); awaiting=df.status.isin(["AWAITING_APPROVAL","IN_REVIEW"]).sum(); escalated=df.status.eq("ESCALATED").sum(); aging1=df.age_days.ge(1).sum(); aging3=df.age_days.ge(3).sum(); c1,c2,c3,c4,c5,c6=st.columns(6); c1.metric("Breaks arrived",f"{len(df):,}"); c2.metric("Resolved",f"{resolved:,}"); c3.metric("Awaiting action",f"{awaiting:,}"); c4.metric("Escalated",f"{escalated:,}"); c5.metric("Age ≥ 1 day",f"{aging1:,}"); c6.metric("Age ≥ 3 days",f"{aging3:,}")
    st.markdown("### Manager attention"); attention=df[(df.severity=="P0")|df.status.isin(["AWAITING_APPROVAL","ESCALATED"])|(df.age_days>=3)].copy().sort_values(["severity","age_days","exposure"],ascending=[True,False,False]).head(10)
    if attention.empty: st.success("No immediate manager attention items in the current snapshot.")
    else:
        attention["Owner"]=attention.family.map({"SETTLEMENT":"Settlements Operations","CASH":"Cash Operations","TRADE":"Trade Support / Middle Office","POSITION":"Position Control"}).fillna("Operations / Middle Office"); attention["Age"]=attention.age_days.astype(int).astype(str)+"d"; attention["Status"]=attention.status.map(lambda s:STATUS_LABEL.get(s,s.replace("_"," ").title())); show=attention[["break_id","Age","severity","exposure","Owner","Status"]].rename(columns={"break_id":"Break","severity":"Priority","exposure":"Exposure (INR)"}); st.dataframe(show,hide_index=True,width="stretch",column_config={"Exposure (INR)":st.column_config.NumberColumn(format="₹%d")})
    g1,g2,g3=st.columns(3)
    with g1:
        age=df.age_bucket.value_counts().reindex(["0 days","1 day","2 days","3 days","4+ days"],fill_value=0); fig=go.Figure(go.Bar(x=age.index,y=age.values,text=age.values,textposition="outside")); fig.update_layout(height=300,margin=dict(l=10,r=10,t=20,b=10),paper_bgcolor=COLORS["surface"],plot_bgcolor=COLORS["surface"]); st.markdown("#### Ageing"); st.plotly_chart(fig,width="stretch")
    with g2:
        fam=df.family.value_counts(); fig=go.Figure(go.Bar(x=fam.index,y=fam.values,text=fam.values,textposition="outside")); fig.update_layout(height=300,margin=dict(l=10,r=10,t=20,b=10),paper_bgcolor=COLORS["surface"],plot_bgcolor=COLORS["surface"]); st.markdown("#### Breaks by category"); st.plotly_chart(fig,width="stretch")
    with g3:
        stat=df.status.map(lambda s:STATUS_LABEL.get(s,s.replace("_"," ").title())).value_counts(); fig=go.Figure(go.Pie(labels=stat.index,values=stat.values,hole=.58,textinfo="label+percent")); fig.update_layout(height=300,margin=dict(l=10,r=10,t=20,b=10),paper_bgcolor=COLORS["surface"],plot_bgcolor=COLORS["surface"]); st.markdown("#### Work status"); st.plotly_chart(fig,width="stretch")
    exposure=df.groupby("family",as_index=False).exposure.sum().sort_values("exposure",ascending=False); exposure["Exposure (₹ Cr)"]=exposure.exposure/1e7; st.markdown("### Exposure by category"); st.dataframe(exposure[["family","Exposure (₹ Cr)"]].rename(columns={"family":"Category"}),hide_index=True,width="stretch"); st.caption(f"Ageing is calculated relative to the latest business date in this reconciliation snapshot ({max_date.date()}).")
