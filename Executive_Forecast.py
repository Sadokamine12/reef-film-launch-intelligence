"""Executive decision brief for Resolution at ESO."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from advanced_ml import empirical_baseline, hybrid_simulation, load_config as flat_config, load_marketing_model, per_show_forecast
from campaign_lab import attribution_readiness, campaign_summary
from model_quality import confidence_summary, current_eso_model, eso_coverage
from project_config import load_config, total_capacity
from ad_targeting_map import planned_zones
from market_context import market_catalog, market_prediction_context
from ui import apply_theme, select_market, INK, MUTED, TEAL, BLUE


def interval(series) -> tuple[int, int, int]:
    return tuple(int(round(series.quantile(q))) for q in (.10, .50, .90))


def card(label: str, number: str, detail: str, note: str = "") -> str:
    return f'<div class="reef-card"><div class="reef-label">{label}</div><div class="reef-number">{number}</div><div class="reef-note">{detail}</div><p>{note}</p></div>'


def forecast_chart(no_paid: tuple[int, int, int], test_plan: tuple[int, int, int], capacity: int) -> go.Figure:
    fig = go.Figure()
    for label, (low, mid, high), color in [
        ("Without paid media", no_paid, BLUE),
        ("With planned tests", test_plan, TEAL),
    ]:
        fig.add_trace(go.Scatter(
            x=[mid], y=[label], mode="markers+text", name=label,
            marker=dict(size=16, color=color), text=[f"{mid} tickets"], textposition="top center",
            textfont=dict(size=14, color=INK),
            error_x=dict(type="data", symmetric=False, array=[high-mid], arrayminus=[mid-low], thickness=4, width=9, color=color),
            hovertemplate=f"{label}<br>Low {low} · Base {mid} · High {high}<extra></extra>",
        ))
    fig.add_vline(x=capacity*.5, line_width=1, line_dash="dot", line_color="#B9C8D1", annotation_text="50%")
    fig.add_vline(x=capacity*.75, line_width=1, line_dash="dot", line_color="#B9C8D1", annotation_text="75%")
    fig.update_layout(
        height=315, showlegend=False, margin=dict(l=20, r=32, t=38, b=42),
        xaxis=dict(title="Tickets across four screenings", range=[0, capacity], gridcolor="#ECF0F3", zeroline=False),
        yaxis=dict(title="", autorange="reversed", tickfont=dict(size=13, color=INK)),
        plot_bgcolor="white", paper_bgcolor="white", font=dict(family="Arial, sans-serif", color=MUTED),
    )
    return fig


def main() -> None:
    st.set_page_config(page_title="Executive Forecast | REEF", page_icon="🎬", layout="wide")
    apply_theme()
    cfg, flat = load_config(), flat_config()
    with st.sidebar:
        st.markdown("### Test market")
        market = select_market()
        st.caption("This changes paid-media geography only. The venue and ESO demand baseline remain fixed in Garching.")
    zones, market_meta = planned_zones(
        cfg["marketing"]["total_budget_eur"],
        cfg["marketing"]["experiment_budget_eur"],
        40,
        market=market,
    )
    capacity = total_capacity(cfg)
    _, empirical, _ = empirical_baseline()
    model = load_marketing_model()
    coverage, eso_model = eso_coverage(), current_eso_model()
    attribution, campaign = attribution_readiness(), campaign_summary()
    confidence = confidence_summary(coverage, eso_model, attribution)
    market_pred = market_prediction_context(market, cfg)
    no_paid_sim, _ = hybrid_simulation(0, model=model, cfg=flat, emp_stats=empirical, n=8000, market=market)
    first_wave_sim, first_wave_allocation = hybrid_simulation(90, model=model, cfg=flat, emp_stats=empirical, n=8000, market=market)
    plan_sim, allocation = hybrid_simulation(cfg["marketing"]["experiment_budget_eur"], model=model, cfg=flat, emp_stats=empirical, n=8000, market=market)
    no_paid = interval(no_paid_sim["total_tickets"])
    first_wave_total = interval(first_wave_sim["total_tickets"])
    first_wave_lift = interval(first_wave_sim["incremental_tickets"])
    with_tests = interval(plan_sim["total_tickets"])
    lift = interval(plan_sim["incremental_tickets"])
    planned_spend = int(allocation["budget_eur"].sum()) if not allocation.empty else 0
    reserve = int(cfg["marketing"]["total_budget_eur"] - planned_spend)
    p50 = float((plan_sim["total_tickets"] >= capacity*.5).mean())
    p75 = float((plan_sim["total_tickets"] >= capacity*.75).mean())
    booking_live = bool(cfg["tracking"].get("resolution_booking_urls"))

    st.markdown(f'''<div class="reef-hero"><div class="reef-eyebrow">REEF Distribution / launch decision brief</div>
      <h1>Resolution at ESO Supernova</h1><p>Four Tuesday screenings · 2–23 February 2027 · {capacity} seats · EUR 500 campaign ceiling · test market: {market["label"]}</p></div>''', unsafe_allow_html=True)
    booking_status = "BOOKING TRACKING CONFIGURED" if booking_live else "PRE-LAUNCH · NO RESOLUTION BOOKINGS"
    st.markdown(f'<span class="reef-pill reef-pill-amber">{booking_status}</span> &nbsp; <span class="reef-pill reef-pill-amber">ATTRIBUTION LEVEL {attribution["level"]}</span> &nbsp; <span class="reef-pill reef-pill-amber">PAID LIFT IS A SCENARIO</span>', unsafe_allow_html=True)
    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

    left, right = st.columns([1.45, 1], gap="medium")
    with left:
        st.markdown(f'''<div class="reef-card"><div class="reef-label">Selected market prediction</div><h3>{market["label"]}</h3>
          <p>Target adults <b>20–60</b> in <b>{", ".join(zones["area"].tolist())}</b>.</p>
          <p><b>EUR 90 first wave:</b> predicted +{first_wave_lift[1]} tickets (low +{first_wave_lift[0]} · high +{first_wave_lift[2]}), for about <b>{first_wave_total[1]} total tickets</b>.</p>
          <p><b>EUR {planned_spend} learning plan:</b> predicted +{lift[1]} tickets, for about <b>{with_tests[1]} total tickets</b>.</p></div>''', unsafe_allow_html=True)
    with right:
        access_detail = f'{market_pred["public_transport_min"]:.0f} min public transport to ESO' if market_pred.get("public_transport_min") is not None else f'{market_pred["distance_to_venue_km"]:.1f} km straight-line distance to ESO'
        pop_detail = f'{market_pred["working_age_population_20_64"]:,} people age 20–64'.replace(",", " ") if market_pred.get("working_age_population_20_64") else "Working-age population not connected"
        st.markdown(f'''<div class="reef-card"><div class="reef-label">Market accessibility</div><div class="reef-number">{market_pred["accessibility"]}</div>
          <p>{access_detail}</p><p>{pop_detail}</p>
          <p>Population is context only. Accessibility remains a <b>planning assumption</b>, not measured city performance.</p></div>''', unsafe_allow_html=True)
    st.markdown(f'<div class="reef-cta"><strong>{market["label"]} scenario:</strong> EUR 90 first wave → +{first_wave_lift[1]} tickets; EUR {planned_spend} learning plan → +{lift[1]} tickets and about {with_tests[1]}/{capacity} total seats filled. Low/base/high total: {with_tests[0]} / {with_tests[1]} / {with_tests[2]}. <strong>Confidence remains low until real campaign and Resolution booking data arrive.</strong></div>', unsafe_allow_html=True)

    st.markdown('## Ticket outlook')
    st.caption(f'Tickets across all four screenings. The selected-city paid scenario is access-adjusted using a transparent distance/transit prior. Low and high are scenario ranges, not calibrated prediction intervals. EUR {reserve} remains unallocated.')
    cols = st.columns(3, gap="medium")
    for col, html in zip(cols, [
        card('Without paid media', str(no_paid[1]), f'Low {no_paid[0]} · High {no_paid[2]} tickets', 'Empirical ESO baseline extrapolated to showtime'),
        card(f'With EUR {planned_spend} learning tests', str(with_tests[1]), f'Low {with_tests[0]} · High {with_tests[2]} tickets', f'Planning scenario; EUR {reserve} held back'),
        card('Additional tickets assumed', f'+{lift[1]}', f'Low +{lift[0]} · High +{lift[2]}', '<span class="reef-pill reef-pill-amber">NOT MEASURED LIFT</span>'),
    ]):
        with col:
            st.markdown(html, unsafe_allow_html=True)

    chart_col, facts_col = st.columns([1.75, 1], gap="large")
    with chart_col:
        st.markdown('### Baseline and test scenario')
        st.plotly_chart(forecast_chart(no_paid, with_tests, capacity), width="stretch", config={"displayModeBar": False})
        st.caption(f'Dots mark the base estimate; horizontal lines show low to high. Paid lift for {market["label"]} is an access-adjusted planning prediction, not measured campaign lift.')
    with facts_col:
        st.markdown('### Decision indicators')
        st.metric('Chance of 50% occupancy', f'{p50:.0%}')
        st.metric('Chance of 75% occupancy', f'{p75:.1%}')
        st.markdown(f'<div class="reef-card"><div class="reef-label">Evidence confidence</div><h3>{confidence["resolution_final"]}</h3><p>Final Resolution sales. Nearest comparable ESO observation: {coverage["lead_min"]:.0f} days before show.</p><p>Paid lift: <b>{confidence["paid_lift"]}</b></p></div>', unsafe_allow_html=True)

    st.markdown('## Compare target-market predictions')
    st.caption('Planning comparison only. Until campaign data exists, differences come from the transparent access prior (distance to ESO plus a small direct-U6 adjustment), not learned market performance.')
    comparison_rows = []
    for name, candidate in market_catalog(cfg).items():
        candidate_meta = market_prediction_context(candidate, cfg)
        candidate_wave, _ = hybrid_simulation(90, model=model, cfg=flat, emp_stats=empirical, n=2500, seed=73, market=candidate)
        candidate_plan, _ = hybrid_simulation(cfg["marketing"]["experiment_budget_eur"], model=model, cfg=flat, emp_stats=empirical, n=2500, seed=73, market=candidate)
        comparison_rows.append({
            "Market": name,
            "Accessibility": candidate_meta["accessibility"],
            "Public transport (min)": int(round(candidate_meta["public_transport_min"])) if candidate_meta.get("public_transport_min") is not None else None,
            "Working-age 20–64": candidate_meta.get("working_age_population_20_64"),
            "Distance to ESO (km)": candidate_meta["distance_to_venue_km"],
            "EUR 90 predicted extra": int(round(candidate_wave["incremental_tickets"].median())),
            f"EUR {int(cfg['marketing']['experiment_budget_eur'])} predicted extra": int(round(candidate_plan["incremental_tickets"].median())),
            "Predicted total tickets": int(round(candidate_plan["total_tickets"].median())),
            "P(50% occupancy)": float((candidate_plan["total_tickets"] >= capacity*.5).mean()),
        })
    import pandas as pd
    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df["Selected"] = comparison_df["Market"].eq(market["label"]).map({True: "●", False: ""})
    display_cols = ["Selected", "Market", "Accessibility", "Public transport (min)", "Working-age 20–64", "Distance to ESO (km)", "EUR 90 predicted extra", f"EUR {int(cfg['marketing']['experiment_budget_eur'])} predicted extra", "Predicted total tickets", "P(50% occupancy)"]
    st.dataframe(
        comparison_df[display_cols].style.format({"Distance to ESO (km)": "{:.1f}", "P(50% occupancy)": "{:.0%}"}),
        hide_index=True, width="stretch",
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=comparison_df["Market"],
        y=comparison_df["EUR 90 predicted extra"],
        text=comparison_df["EUR 90 predicted extra"],
        textposition="outside",
        name="Predicted extra tickets from EUR 90",
    ))
    fig.update_layout(
        height=340, showlegend=False, xaxis_title="", yaxis_title="Scenario incremental tickets",
        plot_bgcolor="white", paper_bgcolor="white", margin=dict(l=40, r=20, t=20, b=80),
        font=dict(color=INK),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.markdown('## Screening-by-screening forecast')
    shows = per_show_forecast(plan_sim, flat)
    st.caption('The four-show total is unchanged, but it is no longer split evenly. The current pre-launch distribution uses transparent calendar + campaign-maturity scenario weights. These are planning assumptions, not measured Tuesday effects.')

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=shows["show_date"],
        y=shows["base"],
        text=[f"{v} · {o:.0f}%" for v, o in zip(shows["base"], shows["occupancy_pct"])],
        textposition="outside",
        marker_color=TEAL,
        error_y=dict(
            type="data", symmetric=False,
            array=(shows["high"] - shows["base"]).tolist(),
            arrayminus=(shows["base"] - shows["low"]).tolist(),
            thickness=2, width=5,
        ),
        hovertemplate="<b>%{x}</b><br>Base %{y} tickets<br>%{text}<extra></extra>",
        name="Base",
    ))
    fig.add_hline(y=cfg["venue"]["capacity_per_show"], line_dash="dot", line_color="#A7B5BF", annotation_text="109-seat capacity")
    fig.update_layout(
        height=390, showlegend=False, xaxis_title="Tuesday screening", yaxis_title="Tickets",
        yaxis_range=[0, cfg["venue"]["capacity_per_show"] + 12],
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=40, r=25, t=25, b=45), font=dict(color=INK),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    cols = st.columns(4, gap="medium")
    for col, (_, row) in zip(cols, shows.iterrows()):
        day = str(row["show_date"])
        with col:
            st.markdown(
                card(
                    f'Tuesday {day[8:10]} February',
                    str(int(row["base"])),
                    f'{row["occupancy_pct"]:.0f}% occupancy · low {int(row["low"])} · high {int(row["high"])}',
                    f'<span class="reef-pill">{"STRONGER CASE" if int(row["scenario_index"]) >= 105 else "SOFTER CASE" if int(row["scenario_index"]) <= 95 else "NEAR BASELINE"}</span><br><br>{row["scenario_driver"]}'
                ),
                unsafe_allow_html=True,
            )

    with st.expander('Why the Tuesday forecasts differ'):
        for _, row in shows.iterrows():
            st.markdown(
                f"**{row['show_date']}:** {row['calendar_fact']}  \n"
                f"*Scenario assumption:* {row['scenario_driver']} (internal factor {int(row['scenario_index'])}, shown here only for methodology)"
            )
        st.caption('The calendar facts are externally verifiable. The direction and size of each weight are modelling assumptions and will be replaced or updated once Resolution-specific sales pace exists.')

    st.markdown('## What changes the decision')
    steps = st.columns(3, gap="medium")
    for col, title, body in zip(steps,
        ['1 · Booking opens', '2 · First EUR 90 test', '3 · Release reserve only if earned'],
        ["Track each Tuesday separately and establish Resolution's no-paid sales pace.",
         'Compare two creatives across three areas using real engagement and tracked sales where valid.',
         'Use measured performance and attribution quality. Keep inefficient budget unspent.']):
        with col:
            st.markdown(f'<div class="reef-card"><h3>{title}</h3><p>{body}</p></div>', unsafe_allow_html=True)

    with st.expander('Evidence and limitations behind these numbers'):
        st.markdown(f'''- **ESO evidence:** {coverage['rows']} booking snapshots from {coverage['unique_shows']} shows. The nearest observation is {coverage['lead_min']:.0f} days before show.
- **Demand model:** grouped MAE {float(eso_model.get('mae') or 0):.1f} occupancy points. It fails the operational gate, so the empirical curve is used.
- **Marketing evidence:** {campaign['rows']} campaign observations; attribution level {attribution['level']}.
- **Planning assumption:** EUR 0.85 per click and 0.045 additional tickets per click. City accessibility now prefers sourced public-transport time where available; otherwise it falls back to distance/access. Working-age population is display context only and does not inflate lift. None of these city effects are learned performance yet.
- **Biggest risk:** no Resolution booking inventory and no comparable observations close to showtime.''')

    st.markdown('### Explore the details')
    links = st.columns(5)
    for col, path, label in zip(links,
        ['pages/1_Sales_Forecast.py', 'pages/2_Ad_Targeting_Map.py', 'pages/3_Campaign_Experiment.py', 'pages/5_Decision_Simulator.py', 'pages/7_Data_Health.py'],
        ['Sales evidence →', 'Targeting map →', 'EUR 500 experiment →', 'Decision simulator →', 'Data health →']):
        with col:
            st.page_link(path, label=label)


if __name__ == '__main__':
    main()
