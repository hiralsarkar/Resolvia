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
    is_open = ~df.status.isin(["CLOSED", "REJECTED"])
    open_count = is_open.sum()
    resolved = (df.status == "CLOSED").sum()
    critical = ((df.severity == "P0") & is_open).sum()
    awaiting = df.status.isin(["AWAITING_APPROVAL", "IN_REVIEW", "AWAITING_VERIFICATION"]).sum()

    st.markdown('<span class="eyebrow">Resolvia Workbench</span>', unsafe_allow_html=True)
    st.markdown('<div class="wb-title">Exception Operations</div>', unsafe_allow_html=True)
    st.markdown('<div class="wb-sub">One place to find the next break, resolve it correctly, and prove what happened.</div>', unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    for col,label,value,sub in [(c1,"Open",open_count,f"of {len(df):,} breaks"),(c2,"Resolved & verified",resolved,f"{resolved/len(df):.0%} of all breaks"),(c3,"Critical, still open",critical,"P0 priority"),(c4,"Waiting on a person",awaiting,"approval, review or verification")]:
        with col:
            st.markdown(f'<div class="wb-card-tight"><div class="wb-label">{label}</div><div class="wb-big">{value:,}</div><div class="wb-muted">{sub}</div></div>',unsafe_allow_html=True)

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
    attention=df[is_open & ((df.severity=="P0") | (df.age_days>=3) | df.status.isin(["AWAITING_APPROVAL","ESCALATED","REOPENED"]))].copy().sort_values(["age_days","exposure"],ascending=False).head(6)
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
    updates=bb.last_updates(); df["last_update"]=df.break_id.map(lambda b:updates.get(b,""))
    n_res=int((df.status=="CLOSED").sum()); n_open=int((~df.status.isin(["CLOSED","REJECTED"])).sum())
    st.markdown(f'<div class="wb-muted" style="margin-bottom:10px"><b style="color:#34E5A6">{n_res:,} resolved</b> ({n_res/len(df):.0%}) · <b>{n_open:,} open</b> · saved automatically, so this survives a reload</div>',unsafe_allow_html=True)
    f0,f1,f2,f3,f4=st.columns([1.3,1.1,1.1,1,1.8])
    show=f0.selectbox("Show",["All breaks","Open work","In progress","Resolved"],key="wb_show")
    fam=f1.multiselect("Category",sorted(df.family.unique()),key="wb_family")
    pri=f2.multiselect("Priority",["P0","P1","P2"],key="wb_priority")
    age=f3.selectbox("Age",["All","Today","1+ day","3+ days"],key="wb_age")
    search=f4.text_input("Search",placeholder="Break ID, security, counterparty",key="wb_search")
    view=df.copy()
    if show=="Open work":view=view[~view.status.isin(["CLOSED","REJECTED"])]
    elif show=="In progress":view=view[~view.status.isin(["CLOSED","REJECTED","NOT_STARTED"])]
    elif show=="Resolved":view=view[view.status=="CLOSED"]
    if fam:view=view[view.family.isin(fam)]
    if pri:view=view[view.severity.isin(pri)]
    if age=="Today":view=view[view.age_days==0]
    elif age=="1+ day":view=view[view.age_days>=1]
    elif age=="3+ days":view=view[view.age_days>=3]
    if search:
        q=search.strip().upper(); view=view[view.apply(lambda r:q in str(r.break_id).upper() or q in str(r.security).upper() or q in str(r.counterparty).upper(),axis=1)]
    total_match=len(view)
    if show=="Resolved":view=view.sort_values("last_update",ascending=False).head(300)
    else:view=view.sort_values(["severity","age_days","exposure"],ascending=[True,False,False]).head(300)
    st.caption(f"{len(view):,} of {total_match:,} matching breaks shown")
    display=view[["break_id","root_cause_key","family","severity","age_days","status","last_update","exposure","counterparty"]].rename(columns={"break_id":"Break","root_cause_key":"Issue","family":"Category","severity":"Priority","age_days":"Age","status":"Status","last_update":"Last update","exposure":"Exposure","counterparty":"Counterparty"})
    display["Issue"]=display.Issue.map(root_cause_label); display["Priority"]=display.Priority.map(lambda x:SEVERITY_LABEL.get(x,x)); display["Status"]=display.Status.map(_status); display["Age"]=display.Age.astype(str)+"d"
    display["Last update"]=pd.to_datetime(display["Last update"],utc=True,errors="coerce").dt.strftime("%d %b %H:%M").fillna("")
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


def render_case_audit(bid,compact=False):
    events=bb.audit_events(break_id=bid,limit=100)
    if not events: st.caption("No activity has been recorded for this break yet.");return
    st.markdown("### Case history" if compact else "### Break audit history")
    rows=[]
    for e in events:
        rows.append({"Time":pd.to_datetime(e["timestamp"],utc=True).strftime("%d %b %Y · %H:%M UTC"),"Operations ID":e.get("actor_id","SYSTEM"),"Action":e.get("action",""),"What was done":e.get("detail","")})
    st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch",height=300 if compact else 520)


def render_audit():
    _css(); st.markdown('<span class="eyebrow">Governance</span>',unsafe_allow_html=True); st.markdown('<div class="wb-title">Audit Trail</div>',unsafe_allow_html=True); st.markdown('<div class="wb-sub">A chronological, append-only record of human and system activity. Stored in the case database, so it survives reloads and restarts.</div>',unsafe_allow_html=True)
    selected=st.session_state.get("audit_break_filter") or st.session_state.get("selected_break")
    f1,f2,f3,f4=st.columns([1.3,1.6,1.6,1])
    operators=f1.multiselect("Operations ID",bb.audit_distinct("actor_id"))
    actions=f2.multiselect("Action",bb.audit_distinct("action"))
    break_options=bb.audit_distinct("break_id"); default=[selected] if selected in break_options else []
    breaks=f3.multiselect("Break",break_options,default=default)
    who=f4.selectbox("Actor",["Everyone","People only","System only"])
    filters=dict(actor_ids=operators or None,actions=actions or None,break_ids=breaks or None)
    s=bb.audit_summary(**filters)
    c1,c2,c3,c4=st.columns(4);c1.metric("Events",f"{s['total']:,}");c2.metric("Human actions",f"{s['human']:,}");c3.metric("Breaks represented",f"{s['breaks']:,}");c4.metric("Approvals",f"{s['approvals']:,}")
    events=bb.audit_events(limit=3000,**filters); df=pd.DataFrame(events)
    if df.empty:st.info("No audit events match these filters.");return
    if who=="People only":df=df[df.actor_id!="SYSTEM"]
    elif who=="System only":df=df[df.actor_id=="SYSTEM"]
    df["timestamp"]=pd.to_datetime(df.timestamp,utc=True)
    out=df.sort_values("timestamp",ascending=False).copy();out["Timestamp"]=out.timestamp.dt.strftime("%d %b %Y · %H:%M:%S UTC");out=out.rename(columns={"actor_id":"Operations ID","break_id":"Break ID","action":"Action","detail":"What was done","source":"Source"});st.dataframe(out[["Timestamp","Operations ID","Break ID","Action","What was done","Source"]],hide_index=True,width="stretch",height=540)
    if s["total"]>len(events):st.caption(f"Showing the latest {len(events):,} of {s['total']:,} events. Filter by break or operator to narrow it down.")
    st.download_button("Download these events (CSV)",out[["Timestamp","Operations ID","Break ID","Action","What was done","Source"]].to_csv(index=False).encode("utf-8"),file_name="resolvia_audit.csv",mime="text/csv")
    if selected:
        st.markdown(f"### Audit for {selected}");render_case_audit(selected)


def render_manager():
    _css(); df=bb.load_breaks_df().copy();df["age_days"]=_age(df);statuses=bb.all_case_statuses();df["status"]=df.break_id.map(lambda b:statuses.get(b,"NOT_STARTED"))
    st.markdown('<span class="eyebrow">Manager Workspace</span>',unsafe_allow_html=True);st.markdown('<div class="wb-title">Operations Overview</div>',unsafe_allow_html=True);st.markdown('<div class="wb-sub">A quick view of workload, ageing, exposure and work that needs attention.</div>',unsafe_allow_html=True)
    vals=[("Arrived",len(df)),("Open",int((~df.status.isin(["CLOSED","REJECTED"])).sum())),("Resolved",int((df.status=="CLOSED").sum())),("Resolved %",f"{(df.status=='CLOSED').mean():.0%}"),("Age ≥ 1 day",int((df.age_days>=1).sum())),("Age ≥ 3 days",int((df.age_days>=3).sum())),("Escalated",int((df.status=="ESCALATED").sum()))]
    cols=st.columns(len(vals))
    for col,(label,val) in zip(cols,vals):
        with col:st.markdown(f'<div class="wb-card-tight"><div class="wb-label">{label}</div><div class="wb-big">{val if isinstance(val,str) else f"{val:,}"}</div></div>',unsafe_allow_html=True)
    st.markdown("### Manager attention")
    att=df[~df.status.isin(["CLOSED","REJECTED"])&((df.severity=="P0")|(df.age_days>=3)|df.status.isin(["AWAITING_APPROVAL","ESCALATED","REOPENED"]))].sort_values(["age_days","exposure"],ascending=False).head(12)
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
