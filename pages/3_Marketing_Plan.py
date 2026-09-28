"""Management campaign plan for Resolution."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from advanced_ml import load_resolution_sales
from launch_strategy import channel_budget, creative_plan, geography_plan, launch_cfg, marketing_timeline, show_plan, today_decision
from project_config import load_config
from ui import apply_theme, page_intro

st.set_page_config(page_title="Campaign Plan | REEF", page_icon="📣", layout="wide")
apply_theme()
page_intro(
    "Commercial execution",
    "Campaign Plan",
    "The operating calendar for when to advertise, where to advertise, how much to release, and when to stop.",
)

cfg=load_config()
launch=launch_cfg(cfg)
resolution=load_resolution_sales()
plan=show_plan(cfg,resolution)
decision=today_decision(plan,cfg)

st.html(
    f"""
    <div style="background:#fff;border:1px solid #DCE5EC;border-radius:10px;padding:13px 15px;margin:4px 0 8px">
      <div style="font-size:9px;font-weight:800;color:#087E83;letter-spacing:.07em">{decision['status']}</div>
      <div style="font-size:16px;font-weight:800;color:#102A43;margin:3px 0">{decision['headline']}</div>
      <div style="font-size:10px;color:#526477">{decision['detail']}</div>
    </div>
    """
)

c1,c2,c3,c4=st.columns(4)
c1.metric("Campaign ceiling","€500")
c2.metric("Controlled first test",f"€{int(launch['initial_test_budget_eur'])}")
c3.metric("Meta ceiling",f"€{int(launch['meta_budget_ceiling_eur'])}")
c4.metric("Google ceiling",f"€{int(launch['google_budget_ceiling_eur'])}")

st.markdown("## When to advertise")
st.dataframe(marketing_timeline(cfg),hide_index=True,width="stretch")
st.success("The €500 is a ceiling, not a spending target. A healthy screening receives €0 extra.")

where_col,budget_col=st.columns([1.2,1],gap="small")
with where_col:
    st.markdown("## Where")
    st.dataframe(geography_plan(),hide_index=True,width="stretch")
    st.caption("Start at ESO/Garching + north Munich. Expand only after the closer catchment has enough delivery and a screening is still behind.")
with budget_col:
    st.markdown("## Budget")
    st.dataframe(channel_budget(cfg),hide_index=True,width="stretch")
    st.caption("Initial test: €70 Meta + €30 Google. The remaining €400 stays conditional and may remain unspent.")

creative_col,rule_col=st.columns([1,1.2],gap="small")
with creative_col:
    st.markdown("## Creative")
    st.dataframe(creative_plan(),hide_index=True,width="stretch")
    st.page_link("pages/4_Creatives.py",label="Open full creative briefs")
with rule_col:
    st.markdown("## 72-hour operating rule")
    st.dataframe(pd.DataFrame([
        ["ON TRACK","Sales ≥ target","€0","Protect budget"],
        ["WATCH","80–99% of target","€8–€12/day","Small 72h correction"],
        ["ACTION","<80% of target","€15–€25/day","Recovery campaign, then review"],
        ["NEAR FULL","≈95–100 sold","€0","Stop that date and promote next Tuesday"],
    ],columns=["State","Trigger","Paid level","Action"]),hide_index=True,width="stretch")

st.markdown("## Measurement checklist")
m1,m2,m3,m4=st.columns(4,gap="small")
items=[
    ("Sales","Tickets sold + remaining seats per Tuesday"),
    ("Timing","Exact campaign start/stop timestamps"),
    ("Media","Spend, impressions, clicks, landing-page visits"),
    ("Attribution","Source/referral data if ESO can provide it"),
]
for col,(title,detail) in zip([m1,m2,m3,m4],items):
    with col:
        st.html(f'<div style="background:#fff;border:1px solid #DCE5EC;border-radius:9px;padding:11px 12px"><b style="font-size:10px;color:#102A43">{title}</b><p style="font-size:9px;color:#526477;margin:4px 0 0">{detail}</p></div>')

st.info("Without purchase-source attribution, the system can still compare total sales pace before/during/after campaigns, but it must not claim that a particular geography caused a particular ticket sale.")
