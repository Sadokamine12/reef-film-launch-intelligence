from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from experiment_protocol import campaign_timeline, attribution_requirements
from project_config import load_config
from ui import apply_theme, page_intro

st.set_page_config(page_title="Resolution Experiment Plan", page_icon="🧪", layout="wide")
apply_theme()
page_intro("Campaign decisions", "EUR 500 Experiment", "A small test first, followed by conditional spending based on measured results.")

cfg = load_config()
plan = pd.read_csv("data/experiment_plan.csv")
timeline = campaign_timeline()

m = cfg["marketing"]
c1,c2,c3,c4 = st.columns(4)
c1.metric("Total budget", f"€{m['total_budget_eur']:.0f}")
c2.metric("Learning budget", f"€{m['experiment_budget_eur']:.0f}")
c3.metric("Protected scale reserve", f"€{m['scale_reserve_eur']:.0f}")
c4.metric("Target", f"{m['success_occupancy_pct']:.0f}%+ occupancy")
st.info("**Current action: EUR 0.** Prepare the six first-wave ads, then record a no-paid Resolution booking window. Release the EUR 90 first wave only after bookings are live; keep the EUR 260 scale reserve conditional.")

st.subheader("Campaign spending sequence")
fig = px.bar(timeline, x="budget_eur", y="name", orientation="h", text="budget_eur", hover_data=["start_date","end_date","action","primary_measure"])
fig.update_layout(height=400, xaxis_title="Planned paid spend (€)", yaxis_title="")
st.plotly_chart(fig, width="stretch")
with st.expander("Dates, dependencies, and measurement for each phase"):
    st.dataframe(timeline, width="stretch", hide_index=True)

st.subheader("First test: three areas × two creatives")
first_wave = plan[plan["wave"].eq("Geo + creative")][["area", "creative", "age_band", "planned_spend_eur"]].copy()
st.dataframe(first_wave.rename(columns={"area":"Area", "creative":"Creative", "age_band":"Audience", "planned_spend_eur":"EUR per cell"}), width="stretch", hide_index=True)
with st.expander("See the full EUR 240 learning plan"):
    st.dataframe(plan, width="stretch", hide_index=True)
    st.caption("Wave 2 areas and creative are selected from first-wave evidence; their placeholders are intentionally unassigned today.")

st.subheader("3. Decision gates — when money is allowed to move")
gates = pd.DataFrame([
    ["After W0", "Resolution booking pages live and 48h no-paid seat movement recorded", "Start paid learning"],
    ["After W1", "Compare geo + creative on CTR/LPV and verified ticket signal if available", "Select top 2 geos + creative"],
    ["After W2", "Age split has enough spend/impressions for a stable direction", "Keep or drop age segmentation"],
    ["Before scale", "Purchase attribution works OR total-seat lift is materially above baseline", "Release part of €260 reserve"],
    ["After each Tuesday", "Actual seat curve vs empirical ESO curve", "Reallocate remaining reserve for next Tuesday"],
], columns=["Gate","Evidence required","Decision"])
st.dataframe(gates, width="stretch", hide_index=True)

st.subheader("4. Attribution — fixed requirement, not a later surprise")
attr = attribution_requirements()
st.dataframe(attr, width="stretch", hide_index=True)
st.error("If ESO provides only total remaining seats and no purchase-source signal, the system can estimate **overall campaign lift**, but it cannot honestly train a ticket-sales model that says Garching ads caused more purchases than Schwabing ads. Geo winner claims require purchase attribution or a controlled source code/report.")

st.subheader("5. Creative protocol")
creative = pd.DataFrame([
    ["A — SXSW proof", "Award / social proof", "Use exactly the same core edit across geos in Wave 1"],
    ["B — Music + 360", "Immersive experience", "Same duration/CTA as A so creative is the main changed variable"],
    ["Scale creative", "Winner from Wave 1", "Use only after measured evidence"],
], columns=["Creative","Message","Rule"])
st.dataframe(creative, width="stretch", hide_index=True)

st.subheader("6. Data captured every day")
st.markdown("""
- ESO remaining seats for each Resolution Tuesday and comparable ESO shows.
- Spend, impressions, 75% video views, clicks and landing-page views by ad set.
- Geo, age band, creative, channel, campaign/ad-set IDs and UTM values.
- Verified ticket label when available, including its **label source**.
- Campaign on/off window and control/baseline periods.

The system trains engagement first. Ticket-lift ML is promoted to operational only after verified ticket labels exist and validation passes.
""")
