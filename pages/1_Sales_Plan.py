"""Sales Plan — actual Resolution pace vs the management booking curve."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from advanced_ml import load_resolution_sales
from launch_strategy import booking_curve_frame, launch_cfg, show_plan
from project_config import load_config
from ui import apply_theme, page_intro, TEAL, BLUE, INK

st.set_page_config(page_title="Sales Plan | REEF", page_icon="🎟️", layout="wide")
apply_theme()
page_intro("Ticket sales", "Sales Plan", "The booking curve, live show pace, forecast range, and the exact action triggered by each screening.")

cfg = load_config()
resolution = load_resolution_sales()
plan = show_plan(cfg, resolution)
launch = launch_cfg(cfg)
curve = booking_curve_frame(cfg)
capacity = int(cfg["venue"]["capacity_per_show"])

c1,c2,c3,c4 = st.columns(4)
c1.metric("Seats per show", capacity)
c2.metric("Final healthy target", f"{int(launch['target_final_tickets_per_show'])}/109")
c3.metric("Ticket launch target", pd.Timestamp(launch["sales_open_target"]).strftime("%d %b %Y"))
c4.metric("First paid test", pd.Timestamp(launch["paid_test_start"]).strftime("%d %b %Y"))

st.markdown("## Healthy booking curve")
fig = go.Figure()
fig.add_trace(go.Scatter(x=curve["days_before_show"], y=curve["target_tickets"], mode="lines+markers", line=dict(color=TEAL,width=4), name="Target"))
if not resolution.empty and {"show_date","tickets_sold","days_to_event"}.issubset(resolution.columns):
    live = resolution.copy()
    if "status" in live:
        live = live[live["status"].astype(str).str.startswith("ok")]
    live["show"] = pd.to_datetime(live["show_date"],errors="coerce").dt.strftime("%d Feb")
    for show, group in live.dropna(subset=["days_to_event","tickets_sold"]).groupby("show"):
        fig.add_trace(go.Scatter(x=group["days_to_event"], y=group["tickets_sold"], mode="lines+markers", name=show))
fig.add_hline(y=capacity,line_dash="dot",line_color="#B9C8D1",annotation_text="109 seats")
fig.update_xaxes(autorange="reversed",title="Days before show")
fig.update_yaxes(title="Tickets sold",range=[0,capacity+8])
fig.update_layout(height=460,plot_bgcolor="white",paper_bgcolor="white",font=dict(color=INK))
st.plotly_chart(fig,width="stretch",config={"displayModeBar":False})
st.caption("The green curve is a management threshold for action. It is not presented as a statistically proven historical law.")

st.markdown("## Four-screening control table")
display = plan.copy()
display["Show"] = pd.to_datetime(display["show_date"]).dt.strftime("%d Feb 2027")
display["Sold"] = display["sold"].apply(lambda x: "—" if pd.isna(x) else f"{int(x)}/109")
display["Target today"] = display["target_today"].apply(lambda x: "—" if pd.isna(x) else int(x))
display["Forecast"] = display.apply(lambda r: "Waiting for live sales" if pd.isna(r["forecast_mid"]) else f"{int(r['forecast_low'])}–{int(r['forecast_high'])} (base {int(r['forecast_mid'])})",axis=1)
display["7d pace"] = display["pace_7d"].apply(lambda x: "—" if pd.isna(x) else f"{float(x):.1f}/day")
display["Paid action"] = display["daily_budget"].apply(lambda x: f"€{int(x)}/day" if int(x)>0 else "€0")
st.dataframe(display[["Show","status","Sold","Target today","7d pace","Forecast","Paid action","recommended_action"]].rename(columns={"status":"Status","recommended_action":"Action"}),hide_index=True,width="stretch")

st.markdown("## Decision checkpoints")
st.dataframe(pd.DataFrame([
    ["60 days", "8+", "Awareness exists; stay organic unless clearly behind"],
    ["45 days", "15+", "Check organic pace and tracking quality"],
    ["30 days", "25+", "Prepare paid test and creative"],
    ["21 days", "38+", "Shows below 80% of target enter ACTION"],
    ["14 days", "55+", "Recovery spend becomes more urgent"],
    ["7 days", "75+", "Focus spend only on the specific weak Tuesday"],
    ["3 days", "88+", "Last-call only if seats remain"],
    ["Show day", "98+", "≈90% occupancy management target"],
],columns=["Checkpoint","Healthy tickets","Management interpretation"]),hide_index=True,width="stretch")

st.info("When a screening reaches roughly 95–100 sold seats, stop advertising it and move the CTA to the next available Tuesday.")
