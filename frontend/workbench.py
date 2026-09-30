"""Resolvia operational workbench.

The interface is intentionally role-first: analysts get a clear next action,
managers get a concise workload view, and auditors get an immediate case
history. The UI uses plain operational language and keeps implementation
details out of the working surface.
"""
import streamlit as st
import pandas as pd

import backend_bridge as bb
from theme import COLORS, STATUS_LABEL, SEVERITY_LABEL, root_cause_label


STAGES = [
    ("triage", "Intake"),
    ("investigation", "Evidence"),
    ("rca", "Cause"),
    ("proposal", "Resolution"),
    ("gate", "Approval"),
    ("post_execution", "Action"),
    ("validation", "Verification"),
]


def _css():
    st.markdown("""
    <style>
    .wb-title {font-size:2.15rem;font-weight:800;letter-spacing:-.04em;margin:0 0 .25rem 0;}
    .wb-sub {color:#8B90A3;font-size:.92rem;margin-bottom:1.2rem;}
    .wb-card {background:#12141D;border:1px solid #232733;border-radius:16px;padding:20px 22px;margin-bottom:14px;}
    .wb-card-tight {background:#12141D;border:1px solid #232733;border-radius:14px;padding:15px 18px;}
    .wb-label {font-size:.67rem;letter-spacing:.1em;text-transform:uppercase;color:#8B90A3;font-weight:700;}
    .wb-big {font-family:'JetBrains Mono',monospace;font-size:1.8rem;font-weight:700;color:#F2F3F8;line-height:1.15;}
    .wb-action {border:1px solid #2b3040;border-radius:12px;padding:14px 16px;background:#171A25;}
    .wb-action strong {font-size:1rem;}
    .wb-muted {color:#8B90A3;font-size:.82rem;}
    .wb-status {font-size:.72rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;}
    .wb-timeline {border-left:2px solid #232733;margin-left:8px;padding-left:18px;}
    .wb-event {padding:0 0 16px 0;position:relative;}
    .wb-event:before {content:"";position:absolute;left:-25px;top:4px;width:8px;height:8px;border-radius:50%;background:#4CE0FF;box-shadow:0 0 8px rgba(76,224,255,.45);}
    .wb-event-time {font-family:'JetBrains Mono',monospace;font-size:.68rem;color:#565B6E;}
    .wb-event-title {font-weight:700;margin-top:2px;}
    .wb-event-detail {color:#8B90A3;font-size:.8rem;margin-top:2px;}
    div[data-testid="stButton"] > button {min-height:44px;font-weight:700;border-radius:10px;}
    div[data-testid="stButton"] > button[kind="primary"] {box-shadow:0 7px 20px rgba(76,224,255,.12);}
    </style>
    """, unsafe_allow_html=True)


def _status(status):
    return STATUS_LABEL.get(status, str(status).replace("_", " ").title())


def _age(df):
    latest = pd.to_datetime(df["business_date"], errors="coerce").max()
    dates = pd.to_datetime(df["business_date"], errors="coerce")
    return (latest - dates).dt.days.clip(lower=0).fillna(0).astype(int)


def _row_for(bid):
    df = bb.load_breaks_df()
    row = df[df.break_id == bid]
    return row.iloc[0] if not row.empty else None


def _open_case(bid):
    st.session_state["selected_break"] = bid
    st.session_state["nav"] = "Case Investigation"
    bb.audit("BREAK_OPENED", bid, "Analyst opened the break")
    st.rerun()


def _open_audit(bid):
    st.session_state["selected_break"] = bid
    st.session_state["audit_break_filter"] = bid
    st.session_state["nav"] = "Audit Trail"
    bb.audit("CASE_AUDIT_OPENED", bid, "Analyst opened the audit history for this break")
    st.rerun()


def render_home():
    _css()
    df = bb.load_breaks_df().copy()
    df["age_days"] = _age(df)
    statuses = bb.all_case_statuses()
    df["status"] = df.break_id.map(lambda b: statuses.get(b, "NOT_STARTED"))
    open_count = (~df.status.isin(["CLOSED", "REJECTED"])).sum()
    critical = (df.severity == "P0").sum()
    old = (df.age_days >= 3).sum()
    awaiting = df.status.isin(["AWAITING_APPROVAL", "IN_REVIEW"]).sum()

    st.markdown('<span class="eyebrow">Resolvia Workbench</span>', unsafe_allow_html=True)
    st.markdown('<div class="wb-title">Exception Operations</div>', unsafe_allow_html=True)
    st.markdown('<div class="wb-sub">One place to find the next break, resolve it correctly, and prove what happened.</div>', unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    for col,label,value in [(c1,"Open",open_count),(c2,"Critical",critical),(c3,"Age ≥ 3 days",old),(c4,"Waiting for approval",awaiting)]:
        with col:
            st.markdown(f'<div class="wb-card-tight"><div class="wb-label">{label}</div><div class="wb-big">{value:,}</div></div>',unsafe_allow_html=True)

    st.markdown("### What do you need to do?")
    a,b,c = st.columns(3)
    with a:
        st.markdown('<div class="wb-action"><div class="wb-label">Analyst</div><strong>Work a break</strong><div class="wb-muted">Find an exception and follow the resolution steps.</div></div>',unsafe_allow_html=True)
        if st.button("Open break queue →",key="home_queue",type="primary",use_container_width=True): st.session_state["nav"]="Operations Desk"; st.rerun()
    with b:
        st.markdown('<div class="wb-action"><div class="wb-label">Manager</div><strong>See the operation</strong><div class="wb-muted">Volume, ageing, exposure and items needing attention.</div></div>',unsafe_allow_html=True)
        if st.button("Open manager view →",key="home_manager",use_container_width=True): st.session_state["nav"]="Manager Dashboard"; st.rerun()
    with c:
        st.markdown('<div class="wb-action"><div class="wb-label">Auditor</div><strong>Trace a case</strong><div class="wb-muted">See who did what, when, and against which break.</div></div>',unsafe_allow_html=True)
        if st.button("Open audit trail →",key="home_audit",use_container_width=True): st.session_state["nav"]="Audit Trail"; st.rerun()

    st.markdown("### Needs attention")
    attention=df[(df.severity=="P0") | (df.age_days>=3) | df.status.isin(["AWAITING_APPROVAL","ESCALATED"])].copy().sort_values(["age_days","exposure"],ascending=False).head(6)
    if attention.empty:
        st.success("Nothing currently requires immediate attention.")
    else:
        for _,r in attention.iterrows():
            cols=st.columns([1.2,1.5,1.1,1.4,.9,.9])
            cols[0].markdown(f'**{r.break_id}**')
            cols[1].markdown(f'{root_cause_label(r.root_cause_key)}')
            cols[2].markdown(f'**{int(r.age_days)}d** old')
            cols[3].markdown(f'₹{r.exposure:,.0f}')
            cols[4].markdown(_status(df.loc[df.break_id==r.break_id,"status"].iloc[0]))
            if cols[5].button("Open",key=f"home_open_{r.break_id}"):_open_case(r.break_id)


def render_operations():
    _css()
    st.markdown('<span class="eyebrow">Analyst Workspace</span>', unsafe_allow_html=True)
    st.markdown('<div class="wb-title">Break Queue</div>', unsafe_allow_html=True)
    st.markdown('<div class="wb-sub">Start with the break that needs your attention. The next action is shown after you open it.</div>', unsafe_allow_html=True)
    df=bb.load_breaks_df().copy(); df["age_days"]=_age(df); statuses=bb.all_case_statuses(); df["status"]=df.break_id.map(lambda b:statuses.get(b,"NOT_STARTED"))
    f1,f2,f3,f4=st.columns([1.2,1.2,1.2,2])
    fam=f1.multiselect("Category",sorted(df.family.unique()),key="wb_family")
    pri=f2.multiselect("Priority",["P0","P1","P2"],key="wb_priority")
    age=f3.selectbox("Age",["All","Today","1+ day","3+ days"],key="wb_age")
    search=f4.text_input("Search",placeholder="Break ID, security, counterparty",key="wb_search")
    view=df.copy()
    if fam:view=view[view.family.isin(fam)]
    if pri:view=view[view.severity.isin(pri)]
    if age=="Today":view=view[view.age_days==0]
    elif age=="1+ day":view=view[view.age_days>=1]
    elif age=="3+ days":view=view[view.age_days>=3]
    if search:
        q=search.strip().upper(); view=view[view.apply(lambda r:q in str(r.break_id).upper() or q in str(r.security).upper() or q in str(r.counterparty).upper(),axis=1)]
    view=view.sort_values(["severity","age_days","exposure"],ascending=[True,False,False]).head(150)
    st.caption(f"{len(view):,} breaks shown")
    display=view[["break_id","root_cause_key","family","severity","age_days","status","exposure","counterparty"]].rename(columns={"break_id":"Break","root_cause_key":"Issue","family":"Category","severity":"Priority","age_days":"Age","status":"Status","exposure":"Exposure","counterparty":"Counterparty"})
    display["Issue"]=display.Issue.map(root_cause_label); display["Priority"]=display.Priority.map(lambda x:SEVERITY_LABEL.get(x,x)); display["Status"]=display.Status.map(_status); display["Age"]=display.Age.astype(str)+"d"
    event=st.dataframe(display,hide_index=True,width="stretch",height=470,on_select="rerun",selection_mode="single-row",key="wb_queue",column_config={"Exposure":st.column_config.NumberColumn(format="₹%d")})
    if event.selection and event.selection.get("rows"):
        bid=display.iloc[event.selection["rows"][0]]["Break"]
        st.session_state["selected_break"]=bid
        row=_row_for(bid)
        st.markdown(f'<div class="wb-card"><div class="wb-label">Selected break</div><div style="font-size:1.35rem;font-weight:800">{bid}</div><div class="wb-muted">{root_cause_label(row.root_cause_key)} · {row.counterparty} · ₹{row.exposure:,.0f}</div></div>',unsafe_allow_html=True)
        x,y,z=st.columns([1.4,1.4,1.4])
        if x.button("Open case →",key="wb_open_selected",type="primary",use_container_width=True):_open_case(bid)
        if y.button("View audit history",key="wb_audit_selected",use_container_width=True):_open_audit(bid)
        if z.button("Resolution guide",key="wb_guide_selected",use_container_width=True):st.session_state["nav"]="Resolution Playbook";st.rerun()


def _case_progress(case):
    parts=[]
    for key,label in STAGES:
        if key=="gate": done=bool(case.get("gate_result",{}).get("authorized")); active=case.get("status")=="AWAITING_APPROVAL"
        else: done=case.get(key) is not None; active=False
        parts.append((label,"done" if done else ("active" if active else "pending")))
    return parts


def render_case():
    _css(); bid=st.session_state.get("selected_break")
    if not bid:
        st.info("Choose a break from the queue first.");
        if st.button("Open break queue →",type="primary"):st.session_state["nav"]="Operations Desk";st.rerun()
        return
    row=_row_for(bid)
    if row is None:st.error("Break not found.");return
    st.markdown('<span class="eyebrow">Case Workspace</span>',unsafe_allow_html=True)
    h1,h2=st.columns([3,1])
    h1.markdown(f'<div class="wb-title">{bid}</div><div class="wb-sub">{root_cause_label(row.root_cause_key)} · {row.counterparty}</div>',unsafe_allow_html=True)
    h2.markdown(f'<div class="wb-label">Exposure</div><div class="wb-big">₹{row.exposure:,.0f}</div>',unsafe_allow_html=True)
    case=bb.get_case(bid)
    if case is None:
        st.markdown('<div class="wb-card"><div class="wb-label">Next step</div><div style="font-size:1.25rem;font-weight:800">Review this break</div><div class="wb-muted">The case will gather the available records, identify the cause, and prepare a resolution path.</div></div>',unsafe_allow_html=True)
        if st.button("Start case review →",key="wb_start_case",type="primary",use_container_width=True):
            with st.status("Reviewing case",expanded=True) as s:
                def on_event(stage,label,detail): st.write(f"{label.replace(' Agent','')}: {detail}")
                bb.get_or_create_case(bid,on_event=on_event)
                s.update(label="Case review complete",state="complete")
            st.rerun()
        return
    bb.audit("CASE_VIEWED",bid,"Analyst viewed the case workspace",dedupe_key=f"case-view:{bid}:{st.session_state.get('nav_cycle',0)}")
    status=case.get("status","CASE_CREATED")
    parts=_case_progress(case)
    progress="".join(f'<span style="display:inline-block;margin-right:6px;padding:7px 10px;border-radius:8px;background:{"rgba(52,229,166,.14)" if s=="done" else "rgba(76,224,255,.12)" if s=="active" else "#171A25"};color:{"#34E5A6" if s=="done" else "#4CE0FF" if s=="active" else "#565B6E"};font-size:.7rem;font-weight:700">{label}</span>' for label,s in parts)
    st.markdown(f'<div style="margin:8px 0 18px">{progress}</div>',unsafe_allow_html=True)
    left,right=st.columns([1.45,.8],gap="large")
    with left:
        rca=case.get("rca") or {}; proposal=case.get("proposal") or {}; inv=case.get("investigation") or {}; triage=case.get("triage") or {}
        st.markdown('<div class="wb-card"><div class="wb-label">What we know</div>',unsafe_allow_html=True)
        c1,c2,c3=st.columns(3); c1.metric("Priority",SEVERITY_LABEL.get(row.severity,row.severity)); c2.metric("Owner",triage.get("route","Operations")); c3.metric("Status",_status(status))
        if rca: st.markdown(f'**Cause:** {root_cause_label(rca.get("root_cause",row.root_cause_key))}<br><span class="wb-muted">Evidence-backed assessment. Certainty: {rca.get("confidence",0)*100:.0f}%</span>',unsafe_allow_html=True)
        if proposal: st.markdown(f'**Recommended next step:** {proposal.get("recommended_action","Review the resolution guidance.")}')
        st.markdown('</div>',unsafe_allow_html=True)
        if inv:
            st.markdown('<div class="wb-card"><div class="wb-label">Evidence</div>',unsafe_allow_html=True)
            se=inv.get("structured_evidence",{})
            for name,key in [("Trade","trade"),("Position","position"),("Settlement","settlement")]:
                if se.get(key):
                    with st.expander(name,expanded=(name=="Trade")):st.dataframe(pd.DataFrame([se[key]]).T.rename(columns={0:"Value"}),width="stretch")
            doc=inv.get("document_evidence",{})
            if doc.get("has_document"): st.markdown(f'**Document:** {doc.get("doc_id","")}\n\n{doc.get("text","")[:1600]}')
            st.markdown('</div>',unsafe_allow_html=True)
    with right:
        st.markdown('<div class="wb-card"><div class="wb-label">What happens next?</div>',unsafe_allow_html=True)
        if status=="AWAITING_APPROVAL": st.markdown('<div style="font-size:1.2rem;font-weight:800">Your approval is required</div><div class="wb-muted">Review the proposed action before anything is carried out.</div>',unsafe_allow_html=True)
        elif status=="CLOSED": st.success("Resolved and verified.")
        elif proposal: st.markdown('<div style="font-size:1.2rem;font-weight:800">Resolution is ready</div><div class="wb-muted">Open the resolution workspace to decide how the fix should be carried out.</div>',unsafe_allow_html=True)
        else: st.markdown('<div style="font-size:1.2rem;font-weight:800">Continue the review</div>',unsafe_allow_html=True)
        if st.button("Resolution workspace →",key="wb_case_resolution",type="primary",use_container_width=True):st.session_state["nav"]="Resolution Control";st.rerun()
        if st.button("Manual resolution guide",key="wb_case_playbook",use_container_width=True):st.session_state["nav"]="Resolution Playbook";st.rerun()
        if st.button("View audit for this break",key="wb_case_audit",use_container_width=True):_open_audit(bid)
        st.markdown('</div>',unsafe_allow_html=True)
    render_case_audit(bid,compact=True)


def render_case_audit(bid,compact=False):
    events=bb.audit_events(break_id=bid,limit=100)
    if not events: st.caption("No activity has been recorded for this break yet.");return
    st.markdown("### Case history" if compact else "### Break audit history")
    rows=[]
    for e in events:
        rows.append({"Time":pd.to_datetime(e["timestamp"],utc=True).strftime("%d %b %Y · %H:%M UTC"),"Operations ID":e.get("actor_id","SYSTEM"),"Action":e.get("action",""),"What was done":e.get("detail","")})
    st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch",height=300 if compact else 520)


def render_resolution():
    _css(); bid=st.session_state.get("selected_break")
    if not bid:st.info("Choose a break first.");return
    case=bb.get_case(bid)
    if not case:st.warning("Review the case before opening the resolution workspace.");return
    row=_row_for(bid); proposal=case.get("proposal") or {}; gate=case.get("gate_result") or {}
    st.markdown('<span class="eyebrow">Decision Workspace</span>',unsafe_allow_html=True); st.markdown(f'<div class="wb-title">Resolve {bid}</div>',unsafe_allow_html=True); st.markdown('<div class="wb-sub">Choose the approved path. Nothing is carried out until the required human decision is recorded.</div>',unsafe_allow_html=True)
    c1,c2,c3=st.columns(3); c1.metric("Issue",root_cause_label(row.root_cause_key)); c2.metric("Status",_status(case.get("status"))); c3.metric("Approval", "Required" if not gate.get("authorized") else "Not required")
    st.markdown('<div class="wb-card">',unsafe_allow_html=True)
    st.markdown("### Proposed resolution")
    st.markdown(proposal.get("recommended_action","No resolution proposal is available yet."))
    if proposal.get("reason"):st.caption(proposal["reason"])
    st.markdown('</div>',unsafe_allow_html=True)
    if case.get("status")=="AWAITING_APPROVAL":
        st.markdown("### Your decision")
        approver=st.text_input("Operations ID",value=st.session_state.get("operator_id","OPS-1047"),key="resolve_approver")
        notes=st.text_area("Decision note",placeholder="What did you verify before approving or rejecting?",key="resolve_notes")
        a,b,c=st.columns(3)
        if a.button("Approve & continue",type="primary",use_container_width=True,key="resolve_approve"):
            bb.approve(bid,approver,notes,mode="Manually by Analyst");st.rerun()
        if b.button("Send to manager",use_container_width=True,key="resolve_escalate"):
            bb.mark(bid,"ESCALATED",approver,notes);st.rerun()
        if c.button("Reject",use_container_width=True,key="resolve_reject"):
            bb.reject(bid,approver,notes);st.rerun()
    elif case.get("status")=="CLOSED":
        st.success("Resolution completed and verification passed.")
    else:
        st.info(f"Current status: {_status(case.get('status'))}")
    if st.button("View this break's audit →",key="resolve_audit"): _open_audit(bid)


def render_playbook():
    _css(); bid=st.session_state.get("selected_break")
    if not bid:st.info("Choose a break first.");return
    case=bb.get_case(bid); row=_row_for(bid)
    st.markdown('<span class="eyebrow">Analyst Guidance</span>',unsafe_allow_html=True); st.markdown(f'<div class="wb-title">Manual resolution · {bid}</div>',unsafe_allow_html=True)
    st.markdown('<div class="wb-sub">A practical checklist for resolving the break when the correction is performed by an analyst.</div>',unsafe_allow_html=True)
    if not case:st.warning("Complete the case review first.");return
    root=(case.get("rca") or {}).get("root_cause",row.root_cause_key)
    playbooks=getattr(__import__("operational_views"),"PLAYBOOKS",{})
    default=getattr(__import__("operational_views"),"DEFAULT_PLAYBOOK")
    owner,escalation,reason,evidence,steps,do_not=playbooks.get(root,default)
    st.markdown(f'<div class="wb-card"><div class="wb-label">Owner</div><div style="font-size:1.2rem;font-weight:800">{owner}</div><div class="wb-muted">Escalation: {escalation}</div><br><strong>{reason}</strong></div>',unsafe_allow_html=True)
    st.markdown("### Do this in order")
    for i,step in enumerate(steps,1):
        st.markdown(f'<div class="wb-card-tight" style="margin-bottom:8px"><b>{i}</b>&nbsp;&nbsp;{step}</div>',unsafe_allow_html=True)
    st.markdown("### Evidence checklist")
    for i,item in enumerate(evidence):st.checkbox(item,key=f"wb_ev_{bid}_{i}")
    st.markdown("### Do not close until")
    for item in do_not:st.warning(item)
    if st.button("Back to case →",key="wb_playbook_back",use_container_width=True):st.session_state["nav"]="Case Investigation";st.rerun()


def render_audit():
    _css(); st.markdown('<span class="eyebrow">Governance</span>',unsafe_allow_html=True); st.markdown('<div class="wb-title">Audit Trail</div>',unsafe_allow_html=True); st.markdown('<div class="wb-sub">A chronological record of human and system activity.</div>',unsafe_allow_html=True)
    selected=st.session_state.get("audit_break_filter") or st.session_state.get("selected_break")
    events=bb.audit_events(limit=2000); df=pd.DataFrame(events)
    if df.empty:st.info("No audit events recorded yet.");return
    df["timestamp"]=pd.to_datetime(df.timestamp,utc=True)
    f1,f2,f3=st.columns([1.4,1.4,2]);
    operators=f1.multiselect("Operations ID",sorted(df.actor_id.dropna().unique())); actions=f2.multiselect("Action",sorted(df.action.dropna().unique()));
    break_options=[x for x in sorted(df.break_id.fillna("").unique()) if x]; default=[selected] if selected in break_options else []
    breaks=f3.multiselect("Break",break_options,default=default)
    if operators:df=df[df.actor_id.isin(operators)]
    if actions:df=df[df.action.isin(actions)]
    if breaks:df=df[df.break_id.isin(breaks)]
    c1,c2,c3,c4=st.columns(4);c1.metric("Events",len(df));c2.metric("Human actions",int((df.actor_id!="SYSTEM").sum()));c3.metric("Breaks represented",df.break_id.replace("",pd.NA).nunique());c4.metric("Approvals",int((df.action=="APPROVAL_GRANTED").sum()))
    out=df.sort_values("timestamp",ascending=False).copy();out["Timestamp"]=out.timestamp.dt.strftime("%d %b %Y · %H:%M:%S UTC");out=out.rename(columns={"actor_id":"Operations ID","break_id":"Break ID","action":"Action","detail":"What was done","source":"Source"});st.dataframe(out[["Timestamp","Operations ID","Break ID","Action","What was done","Source"]],hide_index=True,width="stretch",height=540)
    if selected:
        st.markdown(f"### Audit for {selected}");render_case_audit(selected)


def render_manager():
    _css(); df=bb.load_breaks_df().copy();df["age_days"]=_age(df);statuses=bb.all_case_statuses();df["status"]=df.break_id.map(lambda b:statuses.get(b,"NOT_STARTED"))
    st.markdown('<span class="eyebrow">Manager Workspace</span>',unsafe_allow_html=True);st.markdown('<div class="wb-title">Operations Overview</div>',unsafe_allow_html=True);st.markdown('<div class="wb-sub">A quick view of workload, ageing, exposure and work that needs attention.</div>',unsafe_allow_html=True)
    vals=[("Arrived",len(df)),("Open",int((~df.status.isin(["CLOSED","REJECTED"])).sum())),("Resolved",int((df.status=="CLOSED").sum())),("Age ≥ 1 day",int((df.age_days>=1).sum())),("Age ≥ 3 days",int((df.age_days>=3).sum())),("Escalated",int((df.status=="ESCALATED").sum()))]
    cols=st.columns(6)
    for col,(label,val) in zip(cols,vals):
        with col:st.markdown(f'<div class="wb-card-tight"><div class="wb-label">{label}</div><div class="wb-big">{val:,}</div></div>',unsafe_allow_html=True)
    st.markdown("### Manager attention")
    att=df[(df.severity=="P0")|(df.age_days>=3)|df.status.isin(["AWAITING_APPROVAL","ESCALATED"])].sort_values(["age_days","exposure"],ascending=False).head(12)
    if att.empty:st.success("No items currently require manager attention.")
    else:
        for _,r in att.iterrows():
            cols=st.columns([1.1,1.8,.6,1,.9,.9])
            cols[0].markdown(f"**{r.break_id}**");cols[1].markdown(root_cause_label(r.root_cause_key));cols[2].markdown(f"{r.age_days}d");cols[3].markdown(f"₹{r.exposure:,.0f}");cols[4].markdown(_status(r.status));
            if cols[5].button("Open",key=f"mgr_open_{r.break_id}"):_open_case(r.break_id)
    st.markdown("### Ageing")
    age=df.age_days.value_counts().sort_index(); age=age[age.index<=7]
    st.bar_chart(age)
    st.markdown("### Breaks by category")
    st.bar_chart(df.family.value_counts())
    st.markdown("### Work status")
    st.bar_chart(df.status.map(_status).value_counts())
    st.markdown("### Exposure by category")
    exp=df.groupby("family",as_index=False).exposure.sum().sort_values("exposure",ascending=False);exp["Exposure (₹ Cr)"]=exp.exposure/1e7;st.dataframe(exp[["family","Exposure (₹ Cr)"]].rename(columns={"family":"Category"}),hide_index=True,width="stretch")
