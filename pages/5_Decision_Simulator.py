"""Management-facing scenario simulator for Resolution at ESO."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from advanced_ml import empirical_baseline, hybrid_simulation, load_config as flat_config, load_marketing_model, per_show_forecast
from campaign_lab import attribution_readiness, campaign_summary
from market_context import market_catalog, market_prediction_context
from external_sources import load_external_source_status, source_readiness_rows
from model_quality import eso_coverage
from project_config import load_config, total_capacity
from ui import apply_theme, page_intro, select_market, INK, TEAL, BLUE


def _interval(series) -> tuple[int, int, int]:
    return tuple(int(round(float(series.quantile(q)))) for q in (0.10, 0.50, 0.90))


def _confidence(campaign_rows: int, booking_urls: list, marketing_operational: bool) -> str:
    if marketing_operational and campaign_rows >= 18 and booking_urls:
        return "MEDIUM"
    if campaign_rows >= 6 or booking_urls:
        return "LOW-MEDIUM"
    return "LOW"


st.set_page_config(page_title="Decision Simulator | REEF", page_icon="🎛️", layout="wide")
apply_theme()
page_intro("Management scenario", "Decision Simulator", "Choose a market and budget to see the current planning range. Every output is labelled by evidence type.")

project = load_config()
flat = flat_config()
capacity = total_capacity(project)
_, empirical, _ = empirical_baseline()
marketing = load_marketing_model()
campaign = campaign_summary()
attribution = attribution_readiness()
coverage = eso_coverage()

with st.sidebar:
    st.markdown("### Scenario inputs")
    market = select_market()
    budget = st.slider("Budget ceiling (EUR)", 0, 500, 90, 15)
    days_to_event = st.slider("Campaign starts this many days before first show", 7, 60, 28)
    st.caption("Before controlled lift data exists, the model releases at most the planned EUR 240 learning budget.")

market_meta = market_prediction_context(market, project)
baseline_sim, _ = hybrid_simulation(0, model=marketing, cfg=flat, emp_stats=empirical, days_to_event=days_to_event, n=7000, seed=101, market=market)
sim, allocation = hybrid_simulation(budget, model=marketing, cfg=flat, emp_stats=empirical, days_to_event=days_to_event, n=7000, seed=101, market=market)

baseline = _interval(baseline_sim["total_tickets"])
forecast = _interval(sim["total_tickets"])
lift = _interval(sim["incremental_tickets"])
spent = int(round(float(allocation["budget_eur"].sum()))) if not allocation.empty else 0
held = max(0, budget - spent)
p50 = float((sim["total_tickets"] >= capacity * 0.50).mean())
p60 = float((sim["total_tickets"] >= capacity * 0.60).mean())
p75 = float((sim["total_tickets"] >= capacity * 0.75).mean())
confidence = _confidence(int(campaign.get("rows", 0)), list(project.get("tracking", {}).get("resolution_booking_urls", [])), bool(marketing.operational))

st.markdown(f'''<div class="reef-hero"><div class="reef-eyebrow">Decision simulator</div>
<h1>{market["label"]} · EUR {budget}</h1>
<p>Resolution at ESO Supernova · four screenings · {capacity} total seats · campaign start {days_to_event} days before opening night</p></div>''', unsafe_allow_html=True)

pill = "reef-pill" if confidence != "LOW" else "reef-pill reef-pill-amber"
st.markdown(
    f'<span class="{pill}">FORECAST CONFIDENCE {confidence}</span> &nbsp; '
    f'<span class="reef-pill">BASELINE: EMPIRICAL</span> &nbsp; '
    f'<span class="reef-pill reef-pill-amber">PAID LIFT: SCENARIO</span> &nbsp; '
    f'<span class="reef-pill reef-pill-amber">CITY EFFECT: ASSUMPTION</span>',
    unsafe_allow_html=True,
)
st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("No-paid base", f"{baseline[1]} tickets", f"{baseline[0]}-{baseline[2]}")
m2.metric("Selected plan", f"{forecast[1]} tickets", f"{forecast[0]}-{forecast[2]}")
m3.metric("Scenario lift", f"+{lift[1]} tickets", f"{lift[0]}-{lift[2]}")
m4.metric("Spend released", f"EUR {spent}", f"EUR {held} held")
access_delta = f"{market_meta['public_transport_min']:.0f} min public transport" if market_meta.get("public_transport_min") is not None else f"{market_meta['distance_to_venue_km']:.1f} km to ESO"
m5.metric("Accessibility", market_meta["accessibility"], access_delta)

st.markdown("## Outcome range")
left, right = st.columns([1.7, 1], gap="large")
with left:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["No paid media", f"EUR {spent} released"],
        y=[baseline[1], forecast[1]],
        text=[str(baseline[1]), str(forecast[1])],
        textposition="outside",
        marker_color=[BLUE, TEAL],
        error_y=dict(type="data", symmetric=False, array=[baseline[2] - baseline[1], forecast[2] - forecast[1]], arrayminus=[baseline[1] - baseline[0], forecast[1] - forecast[0]], thickness=2, width=8),
        hovertemplate="%{x}<br>Base %{y} tickets<extra></extra>",
    ))
    fig.add_hline(y=capacity * 0.5, line_dash="dot", line_color="#A7B5BF", annotation_text="50% occupancy")
    fig.add_hline(y=capacity * 0.6, line_dash="dot", line_color="#A7B5BF", annotation_text="60% occupancy")
    fig.update_layout(height=390, showlegend=False, yaxis_title="Tickets across four screenings", yaxis_range=[0, capacity], plot_bgcolor="white", paper_bgcolor="white", margin=dict(l=45, r=25, t=20, b=40), font=dict(color=INK))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
with right:
    st.markdown("### Occupancy probabilities")
    st.metric("Reach 50%", f"{p50:.0%}")
    st.metric("Reach 60%", f"{p60:.0%}")
    st.metric("Reach 75%", f"{p75:.1%}")
    if not marketing.operational:
        st.caption("These probabilities are scenario outputs, not validated marketing probabilities.")

st.markdown("## What is driving this result")
d1, d2, d3, d4 = st.columns(4)
with d1:
    st.markdown(f'''<div class="reef-card"><div class="reef-label">Demand baseline</div><h3>EMPIRICAL</h3>
    <p>{coverage["unique_shows"]} ESO comparable shows currently support the baseline.</p>
    <p>Nearest observation: {coverage["lead_min"]:.0f} days before show.</p></div>''', unsafe_allow_html=True)
with d2:
    travel_line = f'{market_meta["public_transport_min"]:.0f} min public transport to ESO' if market_meta.get("public_transport_min") is not None else f'{market_meta["distance_to_venue_km"]:.1f} km straight-line distance to ESO'
    population_line = f'{market_meta["working_age_population_20_64"]:,} people age 20–64 ({market_meta["working_age_year"]})'.replace(",", " ") if market_meta.get("working_age_population_20_64") else "Working-age population not connected"
    st.markdown(f'''<div class="reef-card"><div class="reef-label">Market context</div><h3>{market_meta["accessibility"]}</h3>
    <p>{travel_line}</p>
    <p>{population_line}</p>
    <p>Population is context only; it does not inflate ticket lift without calibration.</p></div>''', unsafe_allow_html=True)
with d3:
    st.markdown(f'''<div class="reef-card"><div class="reef-label">Marketing evidence</div><h3>{int(campaign.get("rows", 0))} ROWS</h3>
    <p>Ticket-lift model operational: <b>{"yes" if marketing.operational else "no"}</b>.</p>
    <p>Attribution level: <b>{attribution["level"]}</b>.</p></div>''', unsafe_allow_html=True)
with d4:
    st.markdown(f'''<div class="reef-card"><div class="reef-label">Budget control</div><h3>EUR {held} HELD</h3>
    <p>The simulator does not force the full budget into unproven cells.</p>
    <p>Reserve is released only after evidence improves.</p></div>''', unsafe_allow_html=True)

st.markdown("## Screening outlook")
shows = per_show_forecast(sim, flat)
screen_cols = st.columns(4)
for col, (_, row) in zip(screen_cols, shows.iterrows()):
    if int(row["scenario_index"]) >= 105:
        outlook = "STRONGER CASE"
    elif int(row["scenario_index"]) <= 95:
        outlook = "SOFTER CASE"
    else:
        outlook = "NEAR BASELINE"
    with col:
        st.markdown(f'''<div class="reef-card"><div class="reef-label">{row["show_date"]}</div>
        <div class="reef-number">{int(row["base"])}</div>
        <div class="reef-note">{row["occupancy_pct"]:.0f}% occupancy · low {int(row["low"])} · high {int(row["high"])}</div>
        <p><span class="reef-pill">{outlook}</span></p>
        <p>{row["scenario_driver"]}</p></div>''', unsafe_allow_html=True)

st.markdown("## Compare markets at this budget")
rows = []
for name, candidate in market_catalog(project).items():
    meta = market_prediction_context(candidate, project)
    candidate_sim, candidate_alloc = hybrid_simulation(budget, model=marketing, cfg=flat, emp_stats=empirical, days_to_event=days_to_event, n=2400, seed=151, market=candidate)
    candidate_spend = float(candidate_alloc["budget_eur"].sum()) if not candidate_alloc.empty else 0.0
    rows.append({
        "Market": name,
        "Accessibility": meta["accessibility"],
        "Public transport (min)": int(round(meta["public_transport_min"])) if meta.get("public_transport_min") is not None else None,
        "Working-age 20–64": meta.get("working_age_population_20_64"),
        "Distance to ESO (km)": meta["distance_to_venue_km"],
        "Released EUR": int(round(candidate_spend)),
        "Low": int(round(candidate_sim["total_tickets"].quantile(.10))),
        "Base": int(round(candidate_sim["total_tickets"].quantile(.50))),
        "High": int(round(candidate_sim["total_tickets"].quantile(.90))),
        "Scenario extra": int(round(candidate_sim["incremental_tickets"].median())),
        "Evidence": "Scenario prior" if not marketing.operational else "ML + prior",
    })
market_df = pd.DataFrame(rows)
market_df.insert(0, "Selected", market_df["Market"].eq(market["label"]).map({True: "●", False: ""}))
st.dataframe(market_df, hide_index=True, width="stretch")

st.markdown("## Market evidence readiness")
try:
    market_inputs = pd.read_csv("data/market_evidence.csv")
except Exception:
    market_inputs = pd.DataFrame()
selected_input = market_inputs[market_inputs["city"].eq(market["label"])] if (not market_inputs.empty and "city" in market_inputs.columns) else pd.DataFrame()
evidence_fields = [
    ("Working-age population 20–64", "working_age_population_20_64"),
    ("Public-transport time to ESO", "avg_public_transport_min"),
    ("Meta reachable audience", "meta_reachable_audience"),
    ("Google search demand", "google_search_index"),
    ("ESO visitor-origin share", "eso_visitor_origin_share"),
]
readiness = []
for label, field in evidence_fields:
    value = None
    if not selected_input.empty and field in selected_input.columns:
        raw = selected_input.iloc[0][field]
        if pd.notna(raw) and str(raw).strip() != "":
            value = raw
    readiness.append({"Input": label, "Status": "CONNECTED" if value is not None else "NOT CONNECTED", "Value": value if value is not None else "—"})
readiness_df = pd.DataFrame(readiness)
connected = int((readiness_df["Status"] == "CONNECTED").sum())
st.caption(f"{connected}/5 external market inputs connected for {market['label']}. Public demographic and transit evidence is now sourced where available; Meta audience, Google demand and ESO visitor-origin data remain blank until real platform/venue data is supplied.")
st.dataframe(readiness_df, hide_index=True, width="stretch")
if not selected_input.empty:
    row = selected_input.iloc[0]
    source_rows = []
    for label, source_field in [("Population", "population_source"), ("Travel time", "travel_source")]:
        src = str(row.get(source_field, "") or "").strip()
        if src and src.lower() != "nan":
            source_rows.append({"Evidence": label, "Source": src})
    if source_rows:
        with st.expander("Sources for the connected market evidence"):
            st.dataframe(pd.DataFrame(source_rows), hide_index=True, width="stretch")
    note = str(row.get("notes", "") or "").strip()
    if note and note.lower() != "nan":
        st.caption(note)

st.markdown("## Live data connections")
external_status = load_external_source_status()
connection_rows = pd.DataFrame(source_readiness_rows(external_status))
connection_rows["Ready"] = connection_rows["Ready"].map({True: "YES", False: "NO"})
st.dataframe(connection_rows[["Source", "Ready", "Status", "Detail"]], hide_index=True, width="stretch")
if not connection_rows["Ready"].eq("YES").all():
    st.info("The simulator is ready to ingest real ad and booking evidence, but the missing external connections must be completed before the marketing models can learn from live data.")

st.markdown("## What would make this forecast materially better?")
n1, n2, n3 = st.columns(3)
with n1:
    st.markdown('''<div class="reef-card"><div class="reef-label">1 · Resolution sales</div><h3>Four booking URLs</h3>
    <p>Daily seat snapshots let the forecast learn the actual pace of each Tuesday instead of relying on pre-launch priors.</p></div>''', unsafe_allow_html=True)
with n2:
    st.markdown('''<div class="reef-card"><div class="reef-label">2 · Campaign response</div><h3>Meta / Google exports</h3>
    <p>Spend, impressions, clicks, landing-page views and creative IDs allow the engagement model to start learning.</p></div>''', unsafe_allow_html=True)
with n3:
    st.markdown('''<div class="reef-card"><div class="reef-label">3 · Ticket attribution</div><h3>Controlled labels</h3>
    <p>Source codes, purchase events or a staggered/holdout design are required before the app can claim incremental ticket lift.</p></div>''', unsafe_allow_html=True)

with st.expander("Method and limitations"):
    st.markdown(f"""- The no-paid baseline is empirical ESO booking evidence, not the inactive demand ML candidate.
- City accessibility is shown as **HIGH / MEDIUM / LOW** for management. Where a sourced public-transport time is available and marked eligible, it replaces straight-line distance in the scenario friction prior. The internal factor remains an assumption, not a measured city score.
- Sourced working-age population is displayed as market context only. It does not change ticket lift until campaign data can calibrate a relationship between audience pool and conversions.
- Paid-media lift is not learned yet because campaign_history.csv has no usable controlled lift observations.
- The requested budget is a ceiling. Before lift evidence exists, at most EUR {project['marketing']['experiment_budget_eur']} is released into the predefined learning plan.
- Screening differences are calendar/campaign-maturity assumptions until Resolution-specific bookings provide real Tuesday pace.
""")
