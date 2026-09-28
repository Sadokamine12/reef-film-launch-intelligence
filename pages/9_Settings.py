"""Project settings and launch readiness for the Resolution dashboard."""
from __future__ import annotations

import streamlit as st

from project_config import load_config
from ui import apply_theme, editing_enabled, page_intro

st.set_page_config(page_title="Settings | REEF", page_icon="⚙️", layout="wide")
apply_theme()
page_intro(
    "Project configuration",
    "Settings & Readiness",
    "Review the business assumptions, connection status and technical administration for this launch.",
)

cfg = load_config()
launch = cfg.get("launch_plan", {})
tracking = cfg.get("tracking", {})
booking_urls = tracking.get("resolution_booking_urls", [])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Venue capacity", f"{cfg['venue']['capacity_per_show']} / show")
c2.metric("Screenings", len(cfg["screenings"]["dates"]))
c3.metric("Budget ceiling", f"€{cfg['marketing']['total_budget_eur']}")
c4.metric("Cloud mode", "Editable" if editing_enabled() else "View only")

st.markdown("## Launch configuration")
left, right = st.columns(2, gap="small")
with left:
    st.html(
        f"""
        <div style="background:#fff;border:1px solid #DCE5EC;border-radius:10px;padding:14px 16px">
          <div style="font-size:10px;font-weight:800;color:#102A43;margin-bottom:8px">Ticket & campaign timing</div>
          <div style="font-size:10px;color:#526477;line-height:1.65">
            <b>Ticket-sales target:</b> {launch.get('sales_open_target','—')}<br>
            <b>First paid test:</b> {launch.get('paid_test_start','—')} → {launch.get('paid_test_end','—')}<br>
            <b>First-test ceiling:</b> €{launch.get('initial_test_budget_eur','—')}<br>
            <b>Final healthy target:</b> {launch.get('target_final_tickets_per_show','—')} tickets/show
          </div>
        </div>
        """
    )
with right:
    state = "CONNECTED" if len(booking_urls) == 4 else f"{len(booking_urls)}/4 CONNECTED"
    st.html(
        f"""
        <div style="background:#fff;border:1px solid #DCE5EC;border-radius:10px;padding:14px 16px">
          <div style="font-size:10px;font-weight:800;color:#102A43;margin-bottom:8px">Live data readiness</div>
          <div style="font-size:10px;color:#526477;line-height:1.65">
            <b>Resolution booking URLs:</b> {state}<br>
            <b>Campaign source pattern:</b> {tracking.get('utm_source_pattern','—')}<br>
            <b>Campaign name pattern:</b> {tracking.get('utm_campaign_pattern','—')}<br>
            <b>Daily collection:</b> {'Enabled' if tracking.get('daily_collection') else 'Disabled'}
          </div>
        </div>
        """
    )

if len(booking_urls) < 4:
    st.warning("Live Resolution sales cannot start until the four public ESO booking URLs are available and added to the project configuration.")

st.markdown("## Administration")
a1, a2, a3 = st.columns(3, gap="small")
with a1:
    st.page_link("pages/7_Data_Health.py", label="Open data health")
with a2:
    st.page_link("pages/6_Model_Quality.py", label="Open model quality")
with a3:
    st.page_link("pages/8_Evidence_Methodology.py", label="Open evidence methodology")

st.info("The hosted management dashboard is intentionally view-only. Imports, configuration changes and retraining should be made in the controlled project workflow and then published.")
