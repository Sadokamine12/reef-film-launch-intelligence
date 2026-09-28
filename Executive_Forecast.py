"""REEF Resolution Ticket Sales Command Center."""
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
from ui import apply_theme, INK, MUTED, TEAL, BLUE, AMBER


def _status_class(status: str) -> str:
    return {
        "ACTION": "reef-pill-red",
        "WATCH": "reef-pill-amber",
        "ON TRACK": "",
        "PRE-LAUNCH": "",
        "WAITING FOR DATA": "reef-pill-amber",
    }.get(status, "")


def _safe_int(value):
    if pd.isna(value):
        return None
    return int(round(float(value)))


def _sales_chart(curve: pd.DataFrame, capacity: int) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curve["days_before_show"], y=curve["target_tickets"],
        mode="lines+markers", name="Healthy booking curve",
        line=dict(color=TEAL, width=4), marker=dict(size=8),
        hovertemplate="%{x} days before show<br>Target %{y} tickets<extra></extra>",
    ))
    fig.add_hline(y=capacity, line_dash="dot", line_color="#B9C8D1", annotation_text=f"{capacity} seats")
    fig.update_xaxes(autorange="reversed", title="Days before show")
    fig.update_yaxes(title="Tickets sold per screening", range=[0, capacity + 8])
    fig.update_layout(
        height=370, showlegend=False, margin=dict(l=45, r=20, t=25, b=45),
        plot_bgcolor="white", paper_bgcolor="white", font=dict(color=INK),
    )
    return fig


def main() -> None:
    st.set_page_config(page_title="Resolution Command Center | REEF", page_icon="🎬", layout="wide")
    apply_theme()
    cfg = load_config()
    launch = launch_cfg(cfg)
    resolution = load_resolution_sales()
    plan = show_plan(cfg, resolution)
    decision = today_decision(plan, cfg)
    capacity = total_capacity(cfg)

    st.markdown(
        f'''<div class="reef-hero">
          <div class="reef-eyebrow">REEF Distribution / ticket-sales command center</div>
          <h1>Resolution at ESO Supernova</h1>
          <p>4 Tuesday screenings · 2–23 February 2027 · {capacity} total seats · €{int(cfg["marketing"]["total_budget_eur"])} maximum paid-media budget</p>
        </div>''',
        unsafe_allow_html=True,
    )

    # Executive action
    status_cls = _status_class(decision["status"])
    st.markdown(
        f'''<div class="reef-action-card">
          <div class="reef-action-top">
            <div><span class="reef-pill {status_cls}">{decision["status"]}</span></div>
            <div class="reef-action-budget">€{decision["budget"]}/day</div>
          </div>
          <div class="reef-action-title">WHAT SHOULD WE DO TODAY?</div>
          <h2>{decision["headline"]}</h2>
          <p>{decision["detail"]}</p>
          <div class="reef-action-grid">
            <div><span>CHANNEL</span><b>{decision["channel"]}</b></div>
            <div><span>WHERE</span><b>{decision["area"]}</b></div>
            <div><span>NEXT CHECK</span><b>{decision["review"]}</b></div>
          </div>
        </div>''',
        unsafe_allow_html=True,
    )

    # Core KPIs
    sold_total = int(plan["sold"].dropna().sum()) if "sold" in plan else 0
    target_total = int(plan["target_today"].dropna().sum()) if "target_today" in plan else 0
    live_shows = int(plan["sold"].notna().sum()) if "sold" in plan else 0
    cols = st.columns(4, gap="medium")
    metrics = [
        ("Total seats", f"{capacity}", "Across four screenings"),
        ("Tickets observed", f"{sold_total}" if live_shows else "Not live", f"{live_shows}/4 shows connected"),
        ("Healthy target today", f"{target_total}" if target_total else "Pre-launch", "Management booking curve"),
        ("Paid budget ceiling", f"€{int(cfg['marketing']['total_budget_eur'])}", "Spend only when a show needs help"),
    ]
    for col, (label, value, note) in zip(cols, metrics):
        with col:
            st.metric(label, value)
            st.caption(note)

    st.markdown("## Screening control")
    st.caption("Each card answers: Are we on track? What do we expect? Should we advertise this show today?")
    cards = st.columns(4, gap="medium")
    for col, (_, row) in zip(cards, plan.iterrows()):
        show_label = pd.Timestamp(row["show_date"]).strftime("%d Feb")
        sold = _safe_int(row["sold"])
        target = _safe_int(row["target_today"])
        low = _safe_int(row["forecast_low"])
        mid = _safe_int(row["forecast_mid"])
        high = _safe_int(row["forecast_high"])
        status = str(row["status"])
        cls = _status_class(status)
        with col:
            if sold is None:
                big = "—"
                target_text = "No live booking data yet" if status != "PRE-LAUNCH" else "Tickets not on sale yet"
                forecast = "Forecast starts after booking data arrives"
            else:
                big = f"{sold}/109"
                target_text = f"Target today: {target} · Gap: {int(row['gap'])}"
                forecast = f"Forecast: {low}–{high} · base {mid}"
            st.markdown(
                f'''<div class="reef-card">
                  <div class="reef-label">{show_label}</div>
                  <div style="margin:10px 0"><span class="reef-pill {cls}">{status}</span></div>
                  <div class="reef-number">{big}</div>
                  <div class="reef-note">{target_text}</div>
                  <p>{forecast}</p>
                  <p><b>Action:</b> {row["recommended_action"]}</p>
                  <p><b>Paid trigger:</b> €{int(row["daily_budget"])} / day</p>
                </div>''',
                unsafe_allow_html=True,
            )

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        st.markdown("## Healthy booking curve")
        st.caption("This is the management target curve per 109-seat screening. It is a decision threshold, not a claim that history proves this exact shape.")
        st.plotly_chart(_sales_chart(booking_curve_frame(cfg), int(cfg["venue"]["capacity_per_show"])), width="stretch", config={"displayModeBar": False})
    with right:
        st.markdown("## Sales milestones")
        milestones = booking_curve_frame(cfg).sort_values("days_before_show", ascending=False).copy()
        milestones["Checkpoint"] = milestones["days_before_show"].map(lambda x: "Show day" if x == 0 else f"{x} days before")
        milestones["Healthy target"] = milestones["target_tickets"].map(lambda x: f"{x}/109")
        st.dataframe(milestones[["Checkpoint", "Healthy target"]], hide_index=True, width="stretch")
        st.markdown(
            f'''<div class="reef-cta"><strong>Ticket-sale target:</strong> go live around <b>{pd.Timestamp(launch["sales_open_target"]).strftime("%d %b %Y")}</b>, then establish the natural booking pace before the first paid test.</div>''',
            unsafe_allow_html=True,
        )

    st.markdown("## Advertising operating plan")
    t1, t2, t3 = st.tabs(["WHEN", "WHERE", "HOW MUCH"])
    with t1:
        st.dataframe(marketing_timeline(cfg), hide_index=True, width="stretch")
    with t2:
        st.dataframe(geography_plan(), hide_index=True, width="stretch")
        st.caption("Start local. Do not spread a €500 budget across Germany. Expand only if the nearer catchment is efficient and a show still needs demand.")
    with t3:
        budget = channel_budget(cfg)
        st.dataframe(budget, hide_index=True, width="stretch")
        st.metric("Maximum planned budget", f"€{int(budget['Ceiling'].sum())}")
        st.caption("This is a ceiling, not a spending commitment. Healthy shows should receive €0 extra.")

    st.markdown("## Creative plan")
    st.dataframe(creative_plan(), hide_index=True, width="stretch")
    st.info("Keep only two strong creative angles at first. The goal is to learn which message and local catchment produce ticket demand, not to create many unmeasurable ad variants.")

    st.markdown("## Management rules")
    rules = pd.DataFrame([
        ["ON TRACK", "Sales ≥ today's target", "Spend €0 extra; protect the reserve"],
        ["WATCH", "Sales are 80–99% of target", "Small 72-hour correction; re-check before spending more"],
        ["ACTION", "Sales are <80% of target", "72-hour recovery campaign; €15–€25/day depending on urgency"],
        ["NEAR FULL", "A show reaches ~95–100 sold", "Stop advertising that screening and move CTA to the next available Tuesday"],
    ], columns=["Status", "Trigger", "What REEF does"])
    st.dataframe(rules, hide_index=True, width="stretch")

    with st.expander("Analyst view — evidence and limitations"):
        st.markdown(
            """This command center deliberately separates **management thresholds** from **learned evidence**.
The booking curve is an operating target. Live Resolution forecasts become more useful once ESO booking URLs produce daily seat snapshots.
Paid-media lift must remain a scenario until real campaign and attribution data exist. The technical Model Quality, Data Health and Evidence pages remain available for validation."""
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.page_link("pages/1_Sales_Forecast.py", label="Open detailed sales evidence")
        with c2:
            st.page_link("pages/5_Campaign_Data.py", label="Open campaign data")
        with c3:
            st.page_link("pages/6_Model_Quality.py", label="Open model quality")


if __name__ == "__main__":
    main()
