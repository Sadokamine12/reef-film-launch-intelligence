"""Executive decision brief for Resolution at ESO."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from advanced_ml import empirical_baseline, hybrid_simulation, load_config as flat_config, load_marketing_model
from campaign_lab import attribution_readiness, campaign_summary
from model_quality import confidence_summary, current_eso_model, eso_coverage
from project_config import load_config, total_capacity
from ad_targeting_map import planned_zones
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
    no_paid_sim, _ = hybrid_simulation(0, model=model, cfg=flat, emp_stats=empirical, n=8000)
    plan_sim, allocation = hybrid_simulation(cfg["marketing"]["total_budget_eur"], model=model, cfg=flat, emp_stats=empirical, n=8000)
    no_paid, with_tests, lift = (interval(s) for s in (no_paid_sim["total_tickets"], plan_sim["total_tickets"], plan_sim["incremental_tickets"]))
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

    left, right = st.columns([1.6, 1], gap="medium")
    with left:
        st.markdown('''<div class="reef-card"><div class="reef-label">Recommendation</div><h3>Prepare a small, balanced first test</h3>
          <p>Target adults <b>20–60</b> in the three balanced test zones selected for <b>{market["label"]}</b>.</p>
          <p><b>{", ".join(zones["area"].tolist())}</b></p>
          <p>Test <b>SXSW proof</b> against <b>music + 360° experience</b> in each area. Six Meta cells, EUR 15 each. No measured winner exists yet.</p></div>''', unsafe_allow_html=True)
    with right:
        st.markdown('''<div class="reef-card"><div class="reef-label">Money and timing</div><div class="reef-number">EUR 0 now</div>
          <p>Wait for public Resolution bookings. Record 48 hours of seat movement without paid ads.</p>
          <p><b>Then:</b> EUR 90 first wave. Keep EUR 410 available for later decisions.</p></div>''', unsafe_allow_html=True)
    st.markdown(f'<div class="reef-cta"><strong>Selected test market:</strong> {market["label"]}. <strong>Next decision:</strong> 48 hours after bookings open. Check actual sales pace, then start the EUR 90 test. Keep the EUR {reserve} scale reserve conditional.</div>', unsafe_allow_html=True)

    st.markdown('## Ticket outlook')
    st.caption('Tickets across all four screenings. Low and high are scenario ranges, not calibrated prediction intervals. The paid case includes only the EUR 240 learning tests; the reserve stays unallocated.')
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
        st.caption('Dots mark the base estimate; horizontal lines show low to high. The paid difference is an unverified assumption.')
    with facts_col:
        st.markdown('### Decision indicators')
        st.metric('Chance of 50% occupancy', f'{p50:.0%}')
        st.metric('Chance of 75% occupancy', f'{p75:.1%}')
        st.markdown(f'<div class="reef-card"><div class="reef-label">Evidence confidence</div><h3>{confidence["resolution_final"]}</h3><p>Final Resolution sales. Nearest comparable ESO observation: {coverage["lead_min"]:.0f} days before show.</p><p>Paid lift: <b>{confidence["paid_lift"]}</b></p></div>', unsafe_allow_html=True)

    st.markdown('## Four Tuesdays')
    st.caption('No screening has a measured advantage. The current planning case divides the series evenly.')
    cols = st.columns(4, gap="medium")
    for col, day in zip(cols, cfg['screenings']['dates']):
        with col:
            st.markdown(card(f'Tuesday {day[8:10]} February', str(round(with_tests[1]/4)), f'of {cfg["venue"]["capacity_per_show"]} seats · scenario'), unsafe_allow_html=True)

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
- **Planning assumption:** EUR 0.85 per click and 0.045 additional tickets per click, held equal across audiences and creatives. These values are not learned from campaign results.
- **Biggest risk:** no Resolution booking inventory and no comparable observations close to showtime.''')

    st.markdown('### Explore the details')
    links = st.columns(4)
    for col, path, label in zip(links,
        ['pages/1_Sales_Forecast.py', 'pages/2_Ad_Targeting_Map.py', 'pages/3_Campaign_Experiment.py', 'pages/7_Data_Health.py'],
        ['Sales evidence →', 'Targeting map →', 'EUR 500 experiment →', 'Data health →']):
        with col:
            st.page_link(path, label=label)


if __name__ == '__main__':
    main()
