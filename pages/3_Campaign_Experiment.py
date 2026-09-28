"""Marketing Plan — where, when and how much to advertise."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from launch_strategy import channel_budget, creative_plan, geography_plan, launch_cfg, marketing_timeline
from project_config import load_config
from ui import apply_theme, page_intro

st.set_page_config(page_title="Marketing Plan | REEF", page_icon="📣", layout="wide")
apply_theme()
page_intro("Commercial execution", "Marketing Plan", "A practical calendar for where to advertise, when to start, how much to spend, and when to stop.")

cfg = load_config()
launch = launch_cfg(cfg)

c1,c2,c3,c4 = st.columns(4)
c1.metric("Campaign ceiling", "€500")
c2.metric("First paid test", f"€{int(launch['initial_test_budget_eur'])}")
c3.metric("Meta ceiling", f"€{int(launch['meta_budget_ceiling_eur'])}")
c4.metric("Google ceiling", f"€{int(launch['google_budget_ceiling_eur'])}")

st.markdown("## 1. When")
st.dataframe(marketing_timeline(cfg),hide_index=True,width="stretch")
st.success("Default rule: do not spend because budget exists. Spend only when the booking curve says a screening needs help.")

st.markdown("## 2. Where")
st.dataframe(geography_plan(),hide_index=True,width="stretch")
st.markdown("**Primary catchment:** ESO/Garching + north Munich and U6-accessible audiences. **Do not start Germany-wide.** Expand to 30–50 km only after the nearer zones have enough delivery and a show is still behind target.")

st.markdown("## 3. How much")
budget = channel_budget(cfg)
st.dataframe(budget,hide_index=True,width="stretch")
st.caption("The reserve is intentionally uncommitted. It can remain unspent.")

st.markdown("## 4. What to advertise")
st.dataframe(creative_plan(),hide_index=True,width="stretch")
st.markdown("""
**Creative A — Experience:** use the strongest immersive dome/music footage.  
**Creative B — Event:** exact Tuesday, ESO Supernova, Garching/U6, strong ticket CTA.

Keep the two creatives comparable in duration and destination so the result is measurable.
""")

st.markdown("## 5. 72-hour operating rule")
st.dataframe(pd.DataFrame([
    ["ON TRACK","Sales ≥ target","€0","Keep organic/owned activity; protect budget"],
    ["WATCH","80–99% of target","€8–€12/day","Run a small 72-hour correction, then review"],
    ["ACTION","<80% of target","€15–€25/day","Run recovery campaign for the weak Tuesday, then review"],
    ["NEAR FULL","~95–100 tickets","€0","Stop that ad and promote the next available screening"],
],columns=["State","Trigger","Paid level","Action"]),hide_index=True,width="stretch")

st.markdown("## 6. Measurement")
st.markdown("""
Track daily, per screening:
- tickets sold and remaining seats,
- 3-day and 7-day sales pace,
- campaign start/stop timestamps,
- spend, impressions, clicks and landing-page visits by channel,
- geography and creative,
- purchase/source attribution if ESO can provide it.

If purchase attribution is unavailable, the dashboard can still compare total seat pace before/during/after campaigns, but it should not claim that one geography caused a specific ticket sale.
""")
