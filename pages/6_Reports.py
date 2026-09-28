"""Management report for the Resolution launch."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from advanced_ml import load_resolution_sales
from campaign_lab import campaign_summary
from launch_strategy import show_plan, today_decision
from project_config import load_config, total_capacity
from ui import apply_theme, page_intro

st.set_page_config(page_title="Reports | REEF", page_icon="📄", layout="wide", initial_sidebar_state="expanded")
apply_theme()
page_intro("Management reporting", "Reports", "Ticket sales, campaign activity and the next management decision in one concise view.")

cfg = load_config()
resolution = load_resolution_sales()
plan = show_plan(cfg, resolution)
decision = today_decision(plan, cfg)
campaign = campaign_summary()
capacity = total_capacity(cfg)

sold_live = plan["sold"].notna().any()
sold = int(plan["sold"].dropna().sum()) if sold_live else 0

c1,c2,c3,c4 = st.columns(4)
c1.metric("Total capacity", capacity)
c2.metric("Observed sold", sold if sold_live else "Not live")
c3.metric("Campaign observations", int(campaign.get("rows", 0)))
c4.metric("Paid action today", f"€{int(decision['budget'])}/day" if decision["budget"] else "€0")

st.markdown("## Executive decision")
st.info(f"**{decision['headline']}**  
{decision['detail']}")

st.markdown("## Screening status")
report = plan.copy()
report["Show"] = pd.to_datetime(report["show_date"]).dt.strftime("%d %b 2027")
report["Sold"] = report["sold"].apply(lambda x: "—" if pd.isna(x) else int(x))
report["Healthy target"] = report["target_today"].apply(lambda x: "—" if pd.isna(x) else int(x))
report["Paid action"] = report["daily_budget"].apply(lambda x: f"€{int(x)}/day")
st.dataframe(
    report[["Show","status","Sold","Healthy target","Paid action","recommended_action"]].rename(
        columns={"status":"Status","recommended_action":"Action"}
    ),
    hide_index=True,
    width="stretch",
)

st.markdown("## Reporting cadence")
st.dataframe(
    pd.DataFrame([
        ["Daily after ticket launch", "Seat counts, 3/7-day pace, status, next action", "REEF"],
        ["After every 72h paid change", "Spend, clicks, landing visits, ticket pace", "REEF"],
        ["After each Tuesday", "Final occupancy, spend used, learnings", "REEF + ESO"],
        ["End of run", "Campaign ROI, audience/creative learnings, next launch recommendations", "Management"],
    ], columns=["When","Report","Owner"]),
    hide_index=True,
    width="stretch",
)

st.markdown("## Management interpretation")
st.markdown("""
- **No live ticket data:** do not pretend the forecast is observed performance.
- **ON TRACK:** protect budget.
- **WATCH:** run a small 72-hour correction and measure again.
- **ACTION:** run a focused recovery campaign for that specific screening.
- **NEAR FULL:** stop spending on that date and move the CTA to the next Tuesday.
""")

st.caption("Technical model validation and raw import tooling are intentionally kept outside this management report.")
