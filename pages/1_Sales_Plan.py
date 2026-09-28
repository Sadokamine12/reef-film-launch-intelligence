"""Operational ticket-sales page for Resolution."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from advanced_ml import load_resolution_sales
from launch_strategy import booking_curve_frame, launch_cfg, show_plan, today_decision
from project_config import load_config
from ui import apply_theme, page_intro, TEAL, INK

st.set_page_config(page_title="Ticket Sales | REEF", page_icon="🎟️", layout="wide")
apply_theme()
page_intro(
    "Ticket sales",
    "Ticket Sales",
    "One view for the healthy booking curve, each Tuesday's pace, forecast range and the action triggered by the data.",
)

cfg = load_config()
resolution = load_resolution_sales()
plan = show_plan(cfg, resolution)
decision = today_decision(plan, cfg)
launch = launch_cfg(cfg)
curve = booking_curve_frame(cfg)
capacity = int(cfg["venue"]["capacity_per_show"])

st.html(
    f"""
    <div style="background:#fff;border:1px solid #DCE5EC;border-radius:10px;padding:13px 15px;margin:4px 0 8px">
      <div style="font-size:9px;font-weight:800;color:#087E83;letter-spacing:.07em">{decision['status']}</div>
      <div style="font-size:16px;font-weight:800;color:#102A43;margin:3px 0">{decision['headline']}</div>
      <div style="font-size:10px;color:#526477">{decision['detail']}</div>
    </div>
    """
)

c1,c2,c3,c4 = st.columns(4)
c1.metric("Seats per show", capacity)
c2.metric("Healthy finish", f"{int(launch['target_final_tickets_per_show'])}/{capacity}")
c3.metric("Ticket-sales target", pd.Timestamp(launch["sales_open_target"]).strftime("%d %b %Y"))
c4.metric("First paid test", pd.Timestamp(launch["paid_test_start"]).strftime("%d %b %Y"))

left, right = st.columns([1.65, .85], gap="small")
with left:
    st.markdown("## Healthy booking curve")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curve["days_before_show"], y=curve["target_tickets"],
        mode="lines+markers+text", text=curve["target_tickets"], textposition="top center",
        line=dict(color=TEAL,width=3), marker=dict(size=7,color=TEAL), name="Healthy target",
    ))
    if not resolution.empty and {"show_date","tickets_sold","days_to_event"}.issubset(resolution.columns):
        live = resolution.copy()
        if "status" in live:
            live = live[live["status"].astype(str).str.startswith("ok")]
        live["show"] = pd.to_datetime(live["show_date"],errors="coerce").dt.strftime("%d Feb")
        for show, group in live.dropna(subset=["days_to_event","tickets_sold"]).groupby("show"):
            fig.add_trace(go.Scatter(x=group["days_to_event"],y=group["tickets_sold"],mode="lines+markers",name=show))
    fig.add_hline(y=capacity,line_dash="dot",line_color="#B9C8D1",annotation_text="109 seats")
    fig.update_xaxes(autorange="reversed",title="Days before show",gridcolor="#E9EEF2")
    fig.update_yaxes(title="Tickets sold",range=[0,capacity+8],gridcolor="#E9EEF2")
    fig.update_layout(height=370,plot_bgcolor="white",paper_bgcolor="white",font=dict(color=INK,size=10),margin=dict(l=35,r=15,t=15,b=40))
    st.plotly_chart(fig,width="stretch",config={"displayModeBar":False})
    st.caption("The target curve is an operating threshold, not a claim that all ESO shows historically follow exactly this path.")
with right:
    st.markdown("## Milestones")
    milestones = curve.sort_values("days_before_show",ascending=False).copy()
    milestones["Checkpoint"] = milestones["days_before_show"].map(lambda d: "Show day" if d == 0 else f"{int(d)} days before")
    milestones["Healthy"] = milestones["target_tickets"].map(lambda x: f"{int(x)} / {capacity}")
    st.dataframe(milestones[["Checkpoint","Healthy"]],hide_index=True,width="stretch")
    st.info("Once a screening reaches roughly 95–100 sold tickets, stop paid promotion for that date and move the CTA to the next Tuesday.")

st.markdown("## Screening control")
display = plan.copy()
display["Show"] = pd.to_datetime(display["show_date"]).dt.strftime("%d %b 2027")
display["Sold"] = display["sold"].apply(lambda x: "—" if pd.isna(x) else f"{int(x)}/{capacity}")
display["Target"] = display["target_today"].apply(lambda x: "—" if pd.isna(x) else int(x))
display["7d pace"] = display["pace_7d"].apply(lambda x: "—" if pd.isna(x) else f"{float(x):.1f}/day")
display["Forecast"] = display.apply(lambda r: "Waiting for live sales" if pd.isna(r["forecast_mid"]) else f"{int(r['forecast_low'])}–{int(r['forecast_high'])}",axis=1)
display["Paid trigger"] = display["daily_budget"].apply(lambda x: f"€{int(x)}/day")
st.dataframe(
    display[["Show","status","Sold","Target","7d pace","Forecast","Paid trigger","recommended_action"]].rename(columns={"status":"Status","recommended_action":"Action"}),
    hide_index=True,width="stretch"
)

st.markdown("## Operating states")
s1,s2,s3,s4 = st.columns(4,gap="small")
states=[
    ("ON TRACK","At or above target","€0 extra"),
    ("WATCH","80–99% of target","Small 72h correction"),
    ("ACTION","Below 80% of target","€15–€25/day"),
    ("NEAR FULL","≈95–100 sold","Stop that date's ads"),
]
for col,(state,meaning,action) in zip([s1,s2,s3,s4],states):
    with col:
        st.html(f'<div style="background:#fff;border:1px solid #DCE5EC;border-radius:9px;padding:11px 12px"><b style="font-size:10px;color:#102A43">{state}</b><div style="font-size:9px;color:#526477;margin:4px 0">{meaning}</div><strong style="font-size:10px;color:#087E83">{action}</strong></div>')
