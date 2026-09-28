"""Management reporting hub for the Resolution launch."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from advanced_ml import load_resolution_sales
from campaign_lab import campaign_summary, attribution_readiness
from launch_strategy import show_plan, today_decision
from project_config import load_config, total_capacity
from ui import apply_theme, page_intro

st.set_page_config(page_title="Reports | REEF", page_icon="📑", layout="wide")
apply_theme()
page_intro(
    "Management reporting",
    "Launch Reports",
    "A concise view of ticket status, marketing evidence and the next management action.",
)

cfg = load_config()
resolution = load_resolution_sales()
plan = show_plan(cfg, resolution)
decision = today_decision(plan, cfg)
campaign = campaign_summary()
attribution = attribution_readiness()
capacity = total_capacity(cfg)

sold = int(plan["sold"].dropna().sum()) if plan["sold"].notna().any() else 0
live = bool(plan["sold"].notna().any())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Tickets observed", sold if live else "Not live")
c2.metric("Total capacity", capacity)
c3.metric("Published ad spend", f"€{campaign['spend_eur']:.0f}")
c4.metric("Attribution", attribution["level"])

st.markdown("## Management summary")
st.html(
    f"""
    <div style="background:#fff;border:1px solid #DCE5EC;border-radius:10px;padding:15px 17px">
      <div style="font-size:9px;color:#087E83;font-weight:800;letter-spacing:.08em;text-transform:uppercase">{decision['status']}</div>
      <div style="font-size:18px;color:#102A43;font-weight:800;margin:4px 0">{decision['headline']}</div>
      <div style="font-size:10px;color:#526477">{decision['detail']}</div>
    </div>
    """
)

st.markdown("## Screening report")
view = plan.copy()
view["Show"] = pd.to_datetime(view["show_date"]).dt.strftime("%d %b 2027")
view["Sold"] = view["sold"].apply(lambda x: "—" if pd.isna(x) else int(x))
view["Target"] = view["target_today"].apply(lambda x: "—" if pd.isna(x) else int(x))
view["Forecast"] = view.apply(
    lambda r: "Waiting for live sales"
    if pd.isna(r["forecast_mid"])
    else f"{int(r['forecast_low'])}–{int(r['forecast_high'])}",
    axis=1,
)
view["Paid action"] = view["daily_budget"].apply(lambda x: f"€{int(x)}/day")
st.dataframe(
    view[["Show", "status", "Sold", "Target", "Forecast", "Paid action"]].rename(columns={"status": "Status"}),
    hide_index=True,
    width="stretch",
)

st.markdown("## Detailed reports")
r1, r2, r3, r4 = st.columns(4, gap="small")
with r1:
    st.page_link("pages/5_Campaign_Data.py", label="Campaign data")
with r2:
    st.page_link("pages/6_Model_Quality.py", label="Model quality")
with r3:
    st.page_link("pages/7_Data_Health.py", label="Data health")
with r4:
    st.page_link("pages/8_Evidence_Methodology.py", label="Evidence & methodology")

st.caption("Technical validation stays available, but it is intentionally separated from the management command center.")
