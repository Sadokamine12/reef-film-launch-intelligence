"""Decision-oriented spend scenarios and model status."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from advanced_ml import (
    budget_forecast_curve, empirical_baseline, hybrid_simulation, load_config,
    load_marketing_model, load_resolution_sales, next_increment_scenarios,
    per_show_forecast, resolution_pace_forecast,
)
from model_quality import current_eso_model, load_status
from project_config import load_config as load_project_config
from ui import apply_theme, page_intro, select_market, BLUE, TEAL, AMBER, INK

st.set_page_config(page_title="Budget Scenarios | REEF", page_icon="📈", layout="wide")
apply_theme()
page_intro("Planning model", "Budget Scenarios", "See how the outcome changes with spend, while keeping observed data separate from assumptions.")

cfg = load_config()
full = load_project_config()
with st.sidebar:
    st.markdown("### Test market")
    market = select_market()
    st.caption("Paid-media scenarios use this selected market. ESO demand evidence remains venue-specific.")
curve, empirical, _ = empirical_baseline()
marketing = load_marketing_model()
capacity = int(cfg["capacity_per_show"]) * len(cfg["show_dates"])

if not marketing.operational:
    st.warning("Paid ticket lift has no controlled labels. Every paid scenario here uses the same unverified assumption for all areas, ages, channels and creatives. It does not identify a winning ad cell.")

with st.expander("Change scenario inputs"):
    budget = st.slider("Maximum campaign budget (EUR)", 0, 1000, int(cfg["budget_eur"]), 25)
    days_to_event = st.slider("Days before first screening when ads start", 7, 60, 28)
    st.caption("Before lift evidence exists, at most EUR 240 goes to the planned learning tests. Any remainder stays unallocated.")

sim, allocation = hybrid_simulation(budget, model=marketing, cfg=cfg, emp_stats=empirical, days_to_event=days_to_event, n=8000, market=market)
baseline, _ = hybrid_simulation(0, model=marketing, cfg=cfg, emp_stats=empirical, days_to_event=days_to_event, n=8000, market=market)
spent = float(allocation["budget_eur"].sum()) if not allocation.empty else 0.0
low, middle, high = [round(float(sim["total_tickets"].quantile(q))) for q in (.10, .50, .90)]
baseline_mid = round(float(baseline["total_tickets"].median()))
lift_mid = round(float(sim["incremental_tickets"].median()))

cols = st.columns(4)
cols[0].metric("No-paid estimate", f"{baseline_mid} tickets")
cols[1].metric("With planned tests", f"{middle} tickets")
cols[2].metric("Assumed extra", f"+{lift_mid} tickets")
cols[3].metric("Spend released", f"EUR {spent:.0f}", f"EUR {budget-spent:.0f} held")
st.caption(f"Low / base / high: {low} / {middle} / {high} of {capacity} seats. These are planning ranges, not calibrated prediction intervals.")

forecast = budget_forecast_curve(1000, 50, model=marketing, cfg=cfg, emp_stats=empirical, days_to_event=days_to_event, market=market)
tab_spend, tab_screenings, tab_next = st.tabs(["Spend and occupancy", "Four Tuesdays", "Next decision"])

with tab_spend:
    st.markdown("### What changes as the budget ceiling rises?")
    st.caption("The curve flattens after EUR 240 because the conditional reserve is held until results justify its release.")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=forecast["budget_eur"], y=forecast["high_tickets"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=forecast["budget_eur"], y=forecast["low_tickets"], fill="tonexty", fillcolor="rgba(8,126,131,.13)", line=dict(width=0), name="Low to high"))
    fig.add_trace(go.Scatter(x=forecast["budget_eur"], y=forecast["base_tickets"], mode="lines", line=dict(color=TEAL, width=3), name="Base scenario"))
    fig.add_hline(y=capacity*.5, line_dash="dot", line_color="#A7B5BF", annotation_text="50% occupancy")
    fig.add_hline(y=capacity*.75, line_dash="dot", line_color="#A7B5BF", annotation_text="75%")
    fig.update_layout(height=380, xaxis_title="Budget ceiling (EUR)", yaxis_title="Tickets across four screenings", hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white", font=dict(color=INK), margin=dict(l=40, r=25, t=30, b=45))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.markdown("### Chance of reaching occupancy targets")
    fig = go.Figure()
    for target, label, color in [("p50", "50%", TEAL), ("p60", "60%", BLUE), ("p75", "75%", AMBER), ("p90", "90%", "#9965A8"), ("p100", "Sell-out", "#A34545")]:
        fig.add_trace(go.Scatter(x=forecast["budget_eur"], y=forecast[target], mode="lines", name=label, line=dict(width=3, color=color)))
    fig.update_layout(height=340, xaxis_title="Budget ceiling (EUR)", yaxis_title="Scenario probability (%)", yaxis_range=[0, 100], plot_bgcolor="white", paper_bgcolor="white", hovermode="x unified", font=dict(color=INK), margin=dict(l=40, r=25, t=20, b=45))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with st.expander("Compare the requested budget levels"):
        levels = forecast[forecast["budget_eur"].isin([0, 100, 200, 300, 500, 700, 1000])].copy()
        levels = levels.rename(columns={"budget_eur": "Ceiling EUR", "base_tickets": "Base tickets", "low_tickets": "Low", "high_tickets": "High", "extra_tickets": "Assumed extra", "p50": "P(50%)", "p75": "P(75%)"})
        st.dataframe(levels[["Ceiling EUR", "Low", "Base tickets", "High", "Assumed extra", "P(50%)", "P(75%)"]].round(1), hide_index=True, width="stretch")

with tab_screenings:
    st.markdown("### No Tuesday is a proven favorite")
    st.caption("The current data contains no Resolution booking history or credible day-specific advantage. Each Tuesday receives the same planning estimate.")
    shows = per_show_forecast(sim, cfg)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=shows["show_date"], y=shows["base"], name="Base scenario", marker_color=TEAL, error_y=dict(type="data", symmetric=False, array=shows["high"]-shows["base"], arrayminus=shows["base"]-shows["low"])))
    fig.add_hline(y=cfg["capacity_per_show"], line_dash="dot", line_color="#A7B5BF", annotation_text="109 seats")
    fig.update_layout(height=410, yaxis_title="Tickets per screening", xaxis_title="February 2027 screening", plot_bgcolor="white", paper_bgcolor="white", showlegend=False, font=dict(color=INK))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    resolution = load_resolution_sales()
    pace = resolution_pace_forecast(resolution, curve, cfg)
    if pace.empty:
        st.info("Actual Tuesday sales pace will appear when ESO publishes the booking pages and daily tracking begins.")
    else:
        st.subheader("Live Resolution pace")
        st.dataframe(pace, hide_index=True, width="stretch")

with tab_next:
    st.markdown("### Where should the next EUR 25 go?")
    if marketing.operational:
        st.dataframe(next_increment_scenarios(allocation, model=marketing, days_to_event=days_to_event).head(8), hide_index=True, width="stretch")
    else:
        st.info("There is no measured marginal ticket return yet. Run the balanced EUR 90 geography × creative test first. Move the reserve only after results and attribution are reviewed.")
        from experiment_protocol import build_experiment_plan
        plan = build_experiment_plan(market)
        first = plan[plan["wave"].eq("Geo + creative")][["area", "creative", "age_band", "planned_spend_eur"]]
        st.dataframe(first.rename(columns={"area": "Area", "creative": "Creative", "age_band": "Audience", "planned_spend_eur": "EUR per cell"}), hide_index=True, width="stretch")
    with st.expander("Model status and validation"):
        status = load_status()
        for item in status.get("models", []):
            st.markdown(f"**{item['name']}** — {item['status'].replace('_', ' ')}; {item['rows']} rows; operational: {'yes' if item['operational'] else 'no'}.")
        eso = current_eso_model()
        st.caption(f"Demand model grouped MAE {float(eso.get('mae') or 0):.1f} occupancy points. Empirical baseline remains in use until the model passes its quality gate.")
