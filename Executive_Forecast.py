"""Resolution ticket-sales command center for REEF management."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from advanced_ml import load_resolution_sales
from launch_strategy import (
    booking_curve_frame,
    channel_budget,
    creative_plan,
    geography_plan,
    launch_cfg,
    marketing_timeline,
    show_plan,
    today_decision,
)
from project_config import load_config, total_capacity
from ui import apply_theme, INK, MUTED, TEAL, AMBER


def status_class(status: str) -> str:
    return {
        "ON TRACK": "reef-pill-green",
        "WATCH": "reef-pill-amber",
        "ACTION": "reef-pill-red",
        "PRE-LAUNCH": "reef-pill-blue",
        "NEAR FULL": "reef-pill-green",\n        "WAITING FOR DATA": "reef-pill-gray",
    }.get(status, "reef-pill-gray")


def screening_card(row: pd.Series) -> str:
    sold = "—" if pd.isna(row.get("sold")) else str(int(row["sold"]))
    target = "—" if pd.isna(row.get("target_today")) else str(int(row["target_today"]))
    forecast = "Forecast starts after booking data arrives"
    if pd.notna(row.get("forecast_mid")):
        forecast = f'Forecast {int(row["forecast_low"])}–{int(row["forecast_high"])} · base {int(row["forecast_mid"])}'
    trigger = int(row.get("daily_budget") or 0)
    day = pd.Timestamp(row["show_date"]).strftime("%d %b %Y")
    return f"""
    <div class="reef-show-card">
      <div class="reef-show-top"><b>{day}</b><span>Tue</span></div>
      <span class="reef-pill {status_class(str(row["status"]))}">{row["status"]}</span>
      <div class="reef-show-number">{sold}</div>
      <div class="reef-show-sub">sold · healthy target today {target}</div>
      <div class="reef-show-rule">{forecast}</div>
      <div class="reef-show-action"><b>Action:</b> {row["recommended_action"]}</div>
      <div class="reef-show-trigger"><b>Paid trigger:</b> €{trigger}/day</div>
    </div>
    """


def curve_chart(cfg: dict) -> go.Figure:
    curve = booking_curve_frame(cfg).sort_values("days_before_show", ascending=False)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=curve["days_before_show"],
            y=curve["target_tickets"],
            mode="lines+markers+text",
            text=curve["target_tickets"],
            textposition="top center",
            line=dict(color=TEAL, width=4),
            marker=dict(size=9, color=TEAL),
            fill="tozeroy",
            fillcolor="rgba(8,126,131,0.10)",
            hovertemplate="%{x} days before<br>%{y} target tickets<extra></extra>",
        )
    )
    fig.update_xaxes(autorange="reversed", title="Days before screening")
    fig.update_yaxes(title="Target tickets", range=[0, int(cfg["venue"]["capacity_per_show"]) + 12])
    fig.update_layout(
        height=360,
        margin=dict(l=30, r=20, t=20, b=45),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        font=dict(color=MUTED),
    )
    return fig


def main() -> None:
    st.set_page_config(page_title="Resolution Command Center | REEF", page_icon="🎟️", layout="wide")
    apply_theme()
    st.markdown(
        """
        <style>
        .reef-command{padding:26px 30px;border-radius:18px;background:linear-gradient(120deg,#EFF8F8,#F6FAFC);border:1px solid #D6E5E9;margin-bottom:18px}
        .reef-command h2{margin:.2rem 0 .4rem!important;font-size:2rem}
        .reef-command p{color:#526477;margin:.25rem 0}
        .reef-action-box{background:#DFF4EE;border-left:5px solid #087E83;padding:18px 20px;border-radius:12px;margin:15px 0}
        .reef-action-title{font-size:1.3rem;font-weight:760;color:#0B555A}
        .reef-kicker{font-size:.77rem;font-weight:760;letter-spacing:.1em;text-transform:uppercase;color:#087E83}
        .reef-show-card{background:white;border:1px solid #DBE5EB;border-radius:15px;padding:18px;height:100%;box-shadow:0 4px 14px rgba(18,43,66,.03)}
        .reef-show-top{display:flex;justify-content:space-between;gap:8px;color:#14283D;margin-bottom:10px}
        .reef-show-top span{color:#526477;font-size:.82rem}
        .reef-show-number{font-size:2.35rem;font-weight:770;color:#14283D;margin:15px 0 0}
        .reef-show-sub,.reef-show-rule,.reef-show-action,.reef-show-trigger{font-size:.86rem;line-height:1.42;color:#526477;margin-top:7px}
        .reef-show-action{min-height:74px}
        .reef-pill-green{background:#E4F5EC!important;color:#177149!important}
        .reef-pill-blue{background:#E5F0FA!important;color:#245E8A!important}
        .reef-pill-gray{background:#EDF1F4!important;color:#5A6A79!important}
        .reef-section-note{color:#526477;font-size:.9rem;margin-top:-10px;margin-bottom:15px}
        .reef-budget-card{background:white;border:1px solid #DBE5EB;border-radius:14px;padding:18px}
        .reef-budget-value{font-size:1.7rem;font-weight:760;color:#14283D}
        </style>
        """,
        unsafe_allow_html=True,
    )

    cfg = load_config()
    launch = launch_cfg(cfg)
    resolution = load_resolution_sales()
    plan = show_plan(cfg, resolution)
    decision = today_decision(plan, cfg)
    capacity = total_capacity(cfg)
    sold_total = int(plan["sold"].dropna().sum()) if "sold" in plan and plan["sold"].notna().any() else None
    target_total = int(plan["target_today"].dropna().sum()) if "target_today" in plan and plan["target_today"].notna().any() else None

    st.markdown(
        f"""
        <div class="reef-hero">
          <div class="reef-eyebrow">REEF Distribution / management command center</div>
          <h1>Resolution Ticket Sales Command Center</h1>
          <p>4 Tuesday screenings at ESO Supernova · {capacity} total seats · €{int(cfg["marketing"]["total_budget_eur"])} maximum ad budget</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="reef-command">
          <div class="reef-kicker">{decision["status"]}</div>
          <h2>What should we do today?</h2>
          <div class="reef-action-box">
            <div class="reef-action-title">{decision["headline"]}</div>
            <p>{decision["detail"]}</p>
          </div>
          <p><b>Channel:</b> {decision["channel"]} &nbsp;&nbsp; <b>Where:</b> {decision["area"]} &nbsp;&nbsp; <b>Next check:</b> {decision["review"]}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4, gap="medium")
    k1.metric("Total seats", capacity)
    k2.metric("Tickets observed", "Not live" if sold_total is None else sold_total)
    k3.metric("Healthy target today", "Pre-launch" if target_total is None else target_total)
    k4.metric("Paid budget ceiling", f"€{int(cfg['marketing']['total_budget_eur'])}")

    st.markdown("## Screening control")
    st.markdown('<div class="reef-section-note">Each screening gets its own target, forecast and paid trigger. Healthy shows receive €0 extra.</div>', unsafe_allow_html=True)
    cols = st.columns(4, gap="medium")
    for col, (_, row) in zip(cols, plan.iterrows()):
        with col:
            st.markdown(screening_card(row), unsafe_allow_html=True)

    left, right = st.columns([1.55, 1], gap="large")
    with left:
        st.markdown("## Healthy booking curve")
        st.caption("Management target for one 109-seat screening. This is the operating benchmark; the live forecast updates from actual Resolution sales once booking data exists.")
        st.plotly_chart(curve_chart(cfg), width="stretch", config={"displayModeBar": False})
    with right:
        st.markdown("## Sales milestones")
        milestones = booking_curve_frame(cfg).sort_values("days_before_show", ascending=False).copy()
        milestones["Time before"] = milestones["days_before_show"].map(lambda d: "Show day" if d == 0 else f"{d} days before")
        milestones["Target"] = milestones["target_tickets"].map(lambda x: f"{x} / {cfg['venue']['capacity_per_show']}")
        st.dataframe(milestones[["Time before", "Target"]], hide_index=True, width="stretch")
        st.info("Target finish: about 98 / 109 seats per screening. The curve is a management target and is recalibrated when live sales arrive.")

    st.markdown("## Advertising operating plan")
    st.caption("The €500 is a ceiling, not a commitment. We spend only when the booking curve shows a real need.")
    st.dataframe(marketing_timeline(cfg), hide_index=True, width="stretch")

    geo_col, budget_col = st.columns([1.35, 1], gap="large")
    with geo_col:
        st.markdown("### Where to advertise")
        st.dataframe(geography_plan(), hide_index=True, width="stretch")
        st.success("Focus first on Garching + north Munich. Do not advertise broadly across Germany. Expand only if local zones are efficient.")
    with budget_col:
        st.markdown("### How much to spend")
        budget = channel_budget(cfg)
        for _, r in budget.iterrows():
            st.markdown(
                f'<div class="reef-budget-card"><div class="reef-label">{r["Channel"]}</div><div class="reef-budget-value">€{int(r["Ceiling"])}</div><div class="reef-note">{r["Role"]}</div></div><div style="height:10px"></div>',
                unsafe_allow_html=True,
            )
        st.warning("Healthy shows should receive €0 extra. Budget is released only when a screening is behind plan.")

    st.markdown("## Creative plan")
    st.dataframe(creative_plan(), hide_index=True, width="stretch")

    st.markdown("## Management rules")
    rules = pd.DataFrame([
        ["ON TRACK", "Sales at or above target", "Spend €0 extra"],
        ["WATCH", "Sales at 80–99% of target", "Small 72-hour correction"],
        ["ACTION", "Sales below 80% of target", "Recovery campaign, €15–€25/day"],
        ["NEAR FULL", "Around 95–100 sold tickets", "Stop advertising that screening and promote the next Tuesday"],
    ], columns=["Status", "What it means", "Action"])
    st.dataframe(rules, hide_index=True, width="stretch")

    with st.expander("Analyst / model details"):
        st.write("The executive page intentionally hides model-quality metrics. Detailed demand evidence, attribution limits and model validation remain available in the secondary pages.")
        st.page_link("pages/1_Sales_Plan.py", label="Open Sales Plan")
        st.page_link("pages/5_Campaign_Data.py", label="Open Campaign Data")
        st.page_link("pages/6_Model_Quality.py", label="Open Model Quality")
        st.page_link("pages/3_Marketing_Plan.py", label="Open Marketing Plan")


if __name__ == "__main__":
    main()
