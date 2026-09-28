"""Compact management command center for Resolution @ ESO Supernova."""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from advanced_ml import load_resolution_sales
from launch_strategy import booking_curve_frame, launch_cfg, show_plan, today_decision
from project_config import load_config, total_capacity
from ui import apply_theme, INK, MUTED, TEAL


RESOLUTION_IMAGE = "https://reef-distribution.com/wp-content/uploads/2026/03/Resolution_Square-768x768.jpg"
RESOLUTION_POSTER = "https://reef-distribution.com/wp-content/uploads/2026/03/POSTER_withCredits_40X27CinephonicTagline-768x1138.jpg"
ESO_IMAGE = "https://supernova.eso.org/static/archives/images/screen/PANO0003-CC.jpg"


def e(value: object) -> str:
    return escape(str(value), quote=True)


def status_class(status: str) -> str:
    return {
        "ON TRACK": "reef-pill-green",
        "WATCH": "reef-pill-amber",
        "ACTION": "reef-pill-red",
        "PRE-LAUNCH": "reef-pill-blue",
        "NEAR FULL": "reef-pill-green",
        "WAITING FOR DATA": "reef-pill-gray",
    }.get(status, "reef-pill-gray")


def screening_card(row: pd.Series) -> str:
    sold = "—" if pd.isna(row.get("sold")) else str(int(row["sold"]))
    forecast = "Forecast starts after booking data arrives"
    if pd.notna(row.get("forecast_mid")):
        forecast = f'{int(row["forecast_low"])}–{int(row["forecast_high"])} expected · base {int(row["forecast_mid"])}'
    trigger = int(row.get("daily_budget") or 0)
    date_label = pd.Timestamp(row["show_date"]).strftime("%d %b")
    action = str(row["recommended_action"])
    if row["status"] == "PRE-LAUNCH":
        action = "Prepare booking launch, tracking and creative"
    return f"""
      <div class="show-mini">
        <div class="show-date"><b>{date_label}</b><span>Tue</span></div>
        <span class="reef-pill {status_class(str(row["status"]))}">{e(row["status"])}</span>
        <div class="show-sold">{sold}</div>
        <div class="show-main">{"Tickets not on sale yet" if sold == "—" else "tickets sold"}</div>
        <div class="show-muted">{e(forecast)}</div>
        <div class="show-action"><b>Action:</b> {e(action)}</div>
        <div class="show-trigger"><b>Paid trigger:</b> €{trigger}/day</div>
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
            textfont=dict(size=9, color=INK),
            line=dict(color="#0AA7B5", width=2.5),
            marker=dict(size=6, color="#0AA7B5"),
            fill="tozeroy",
            fillcolor="rgba(10,167,181,.09)",
            hovertemplate="%{x} days before<br>%{y} target tickets<extra></extra>",
        )
    )
    fig.update_xaxes(
        autorange="reversed",
        title="Days before screening",
        tickvals=[60,45,30,21,14,7,3,0],
        ticktext=["60","45","30","21","14","7","3","Show day"],
        title_font=dict(size=9),
        tickfont=dict(size=8),
        gridcolor="#E8EEF3",
        zeroline=False,
    )
    fig.update_yaxes(
        title="Tickets sold",
        range=[0, int(cfg["venue"]["capacity_per_show"]) + 12],
        title_font=dict(size=9),
        tickfont=dict(size=8),
        gridcolor="#E8EEF3",
        zeroline=False,
    )
    fig.update_layout(
        height=225,
        margin=dict(l=34, r=8, t=14, b=36),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        font=dict(color=MUTED, size=9),
    )
    return fig


def milestones_html(cfg: dict) -> str:
    curve = booking_curve_frame(cfg).sort_values("days_before_show", ascending=False)
    rows = []
    for _, r in curve.iterrows():
        day = int(r["days_before_show"])
        label = "Show day" if day == 0 else f"{day} days before"
        rows.append(f"<tr><td>{label}</td><td>{int(r['target_tickets'])} / {cfg['venue']['capacity_per_show']}</td></tr>")
    return "<table class='mini-table'><thead><tr><th>Time before</th><th>Target</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def operating_plan_html() -> str:
    rows = [
        ("1","Now → 15 Nov 2026","Launch readiness","€0","Confirm ESO ticket launch, booking URLs, UTMs, and two creatives"),
        ("2","16 Nov 2026 → 3 Jan 2027","Organic baseline","€0","Sell tickets organically and observe natural booking pace"),
        ("3","4 Jan 2027 → 10 Jan 2027","Controlled paid test","€100","Meta €70 + Google €30"),
        ("4","11 Jan 2027 → 31 Jan 2027","Conditional scaling","Only if behind curve","Move spend only to weak screenings"),
        ("5","1 Feb 2027 → 23 Feb 2027","Show-specific recovery","€8–€25/day","Advertise only the screening that needs help"),
    ]
    body = "".join(
        f"""<div class="plan-row">
          <div class="plan-num">{n}</div>
          <div><b>{period}</b><span>Goal: {goal}</span></div>
          <div><span>Paid ceiling:</span><b>{ceiling}</b></div>
          <div><span>Action:</span>{action}</div>
        </div>"""
        for n, period, goal, ceiling, action in rows
    )
    return f"""
      <div class="section-title">📣 &nbsp;Advertising Operating Plan</div>
      <div class="segmented"><b>When</b><span>Where</span><span>How Much</span></div>
      <div class="plan-list">{body}</div>
    """


def geography_html() -> str:
    return """
      <div class="section-title">📍 &nbsp;Where to Advertise</div>
      <div class="geo-wrap">
        <div class="rings">
          <div class="ring ring50"></div>
          <div class="ring ring30"></div>
          <div class="ring ring15"></div>
          <div class="eso-dot">◆<span>ESO<br>Supernova</span></div>
          <span class="ring-label l50">50 km</span>
          <span class="ring-label l30">30 km</span>
          <span class="ring-label l15">15 km</span>
          <span class="city-label garching">Garching</span>
          <span class="city-label munich">Munich</span>
        </div>
        <div class="zone-list">
          <div><i class="z1"></i><b>Zone A — Core</b><span>0–15 km from ESO<br>Highest priority · <strong>50%</strong></span></div>
          <div><i class="z2"></i><b>Zone B — Munich catchment</b><span>15–30 km<br>High priority · <strong>35%</strong></span></div>
          <div><i class="z3"></i><b>Zone C — Expansion</b><span>30–50 km<br>Test only · <strong>15%</strong></span></div>
        </div>
      </div>
      <div class="check">● Focus on Garching + North Munich</div>
      <div class="check">● Do not advertise broadly across Germany</div>
      <div class="check">● Expand only if local zones are efficient</div>
    """


def budget_html() -> str:
    return """
      <div class="section-title">☷ &nbsp;How Much to Spend</div>
      <div class="budget-row"><span class="budget-logo meta">∞</span><div>Meta / Instagram / Facebook</div><b>€300</b></div>
      <div class="budget-row"><span class="budget-logo google">G</span><div>Google Search</div><b>€125</b></div>
      <div class="budget-row"><span class="budget-logo reserve">▥</span><div>Tactical reserve</div><b>€75</b></div>
      <div class="budget-note"><b>Healthy shows should receive €0 extra.</b><br>Budget is a ceiling, not a spending commitment.</div>
    """


def creative_html() -> str:
    return f"""
      <div class="section-title">▣ &nbsp;Creative Plan</div>
      <div class="creative-grid">
        <div class="creative-item">
          <img src="{RESOLUTION_POSTER}" alt="Resolution artwork">
          <div><b>Creative A — Experience</b><span>Message: immersive music + light + dome experience</span><small>Use: broad discovery / reels / stories</small></div>
        </div>
        <div class="creative-item">
          <img src="{ESO_IMAGE}" alt="ESO Supernova">
          <div><b>Creative B — Event</b><span>Resolution at ESO Supernova, exact Tuesday, Garching/U6, ticket CTA</span><small>Use: local event conversion</small></div>
        </div>
      </div>
    """


def rules_html() -> str:
    return """
      <div class="section-title">⚙ &nbsp;Management Rules</div>
      <table class="rules-table">
        <thead><tr><th>Status</th><th>What it means</th><th>Action</th></tr></thead>
        <tbody>
          <tr><td><i class="dot green"></i><b>ON TRACK</b></td><td>Sales at or above target</td><td>Spend €0 extra</td></tr>
          <tr><td><i class="dot amber"></i><b>WATCH</b></td><td>Sales at 80–99% of target</td><td>Small 72-hour correction</td></tr>
          <tr><td><i class="dot red"></i><b>ACTION</b></td><td>Sales below 80% of target</td><td>Recovery campaign, €15–€25/day</td></tr>
          <tr><td><i class="dot blue"></i><b>NEAR FULL</b></td><td>Around 95–100 sold tickets</td><td>Stop that ad and promote next Tuesday</td></tr>
        </tbody>
      </table>
    """


def main() -> None:
    st.set_page_config(
        page_title="Resolution Command Center | REEF",
        page_icon="🎟️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()
    st.markdown(
        """
<style>
.main-title-row{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin:3px 0 9px}
.main-sub{font-size:12px;color:#29455E;margin-top:3px}
.main-sub b{color:#102A43}
.venue-id{display:flex;align-items:center;gap:9px;font-size:9px;color:#23445F;line-height:1.25;text-align:left}
.venue-logo{font-size:27px;color:#244F70}
.topbar{height:34px;margin:-10px -18px 8px;padding:0 18px;border-bottom:1px solid #E1E8EE;background:white;display:flex;justify-content:flex-end;align-items:center;gap:7px}
.top-chip{border:1px solid #E1E8EE;background:#FBFCFD;border-radius:7px;padding:5px 9px;font-size:9px;color:#24425D}
.top-avatar{width:23px;height:23px;border-radius:50%;display:inline-grid;place-items:center;background:#11344E;color:white;font-size:8px;font-weight:800}
.hero-img{height:200px;border-radius:9px;background-size:cover;background-position:center;position:relative;overflow:hidden}
.hero-img:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(4,17,31,.05),rgba(4,17,31,.72))}
.hero-film-title{position:absolute;z-index:2;left:22px;top:20px;color:white;font-family:Georgia,serif;letter-spacing:.22em;font-size:19px}
.hero-film-sub{position:absolute;z-index:2;left:24px;top:47px;color:#D8E5EE;font-size:8px;letter-spacing:.11em}
.hero-film-venue{position:absolute;z-index:2;left:16px;bottom:12px;color:white;font-size:7px;line-height:1.28;letter-spacing:.04em}
.action-panel{height:200px;border-radius:9px;background:linear-gradient(105deg,#EDF8FB,#E7F5FC);padding:13px 16px;box-sizing:border-box}
.action-panel h2{font-size:25px!important;margin:5px 0 8px!important;color:#102A43}
.action-line{background:#D7F3EC;border-radius:7px;padding:8px 12px;color:#075B55;font-size:15px;font-weight:800}
.action-detail{font-size:10px;color:#304A61;margin:6px 0 8px}
.action-meta{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
.action-meta div{background:rgba(255,255,255,.78);border:1px solid #E2EAF0;border-radius:7px;padding:8px 10px;font-size:9px;line-height:1.25;color:#23425D}
.action-meta b{display:block;color:#183A55;font-size:9px;margin-bottom:2px}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:8px 0 10px}
.kpi{background:white;border:1px solid #DCE5EC;border-radius:8px;padding:9px 12px;display:flex;align-items:center;gap:12px;min-height:54px}
.kpi-icon{font-size:21px;width:34px;text-align:center;color:#083D5E}
.kpi small{display:block;font-size:9px;color:#3F566A}
.kpi b{display:block;font-size:19px;color:#102A43;margin-top:2px}
.dash-card{background:#fff;border:1px solid #DCE5EC;border-radius:8px;padding:9px 10px;height:100%;box-sizing:border-box}
.section-title{font-size:13px;font-weight:800;color:#102A43;margin-bottom:7px}
.screen-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:7px}
.screen-head a{font-size:8px;color:#315C7D}
.show-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}
.show-mini{border:1px solid #DFE7ED;border-radius:7px;padding:9px;min-height:187px}
.show-date{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:#102A43;margin-bottom:5px}
.show-date span{font-size:8px;color:#526477}
.show-sold{font-size:23px;font-weight:800;color:#102A43;margin:9px 0 0}
.show-main{font-size:9px;font-weight:700;color:#18364F;margin-bottom:7px}
.show-muted{font-size:8px;color:#6B7F90;min-height:23px}
.show-action{font-size:8px;line-height:1.35;color:#31506A;min-height:38px;margin-top:6px}
.show-trigger{font-size:8px;color:#24445F;margin-top:7px}
.mini-table,.rules-table{width:100%;border-collapse:collapse;font-size:8px;color:#28455D}
.mini-table th,.mini-table td,.rules-table th,.rules-table td{border:1px solid #DFE7ED;padding:4px 5px;text-align:left}
.mini-table th,.rules-table th{background:#F5F8FA;color:#405B70;font-weight:700}
.segmented{display:grid;grid-template-columns:1fr 1fr 1fr;border-radius:6px;overflow:hidden;background:#EAF3F7;margin-bottom:7px;font-size:8px;text-align:center}
.segmented>*{padding:5px}.segmented b{background:#174D72;color:white}
.plan-row{display:grid;grid-template-columns:24px 1.35fr .95fr 1.45fr;gap:6px;align-items:center;border-bottom:1px solid #E8EDF1;padding:5px 2px;font-size:7.5px;color:#315069}
.plan-row:last-child{border-bottom:0}
.plan-row b{display:block;color:#163A55;font-size:8px}
.plan-row span{display:block;color:#6B7D8B;font-size:7px}
.plan-num{width:19px;height:19px;border-radius:50%;display:grid;place-items:center;background:#087E83;color:white;font-weight:800;font-size:8px}
.geo-wrap{display:grid;grid-template-columns:1.1fr .9fr;gap:8px;align-items:center}
.rings{height:160px;position:relative;background:linear-gradient(135deg,#F2F6EF,#E9F1F3);border-radius:7px;overflow:hidden}
.ring{position:absolute;border-radius:50%;left:50%;top:50%;transform:translate(-50%,-50%);border:1px solid rgba(8,126,131,.18)}
.ring50{width:142px;height:142px;background:rgba(98,205,212,.16)}
.ring30{width:103px;height:103px;background:rgba(67,192,204,.18)}
.ring15{width:65px;height:65px;background:rgba(8,126,131,.22)}
.eso-dot{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);color:#092B44;font-size:13px;text-align:center;z-index:2}
.eso-dot span{display:block;font-size:7px;font-weight:800;line-height:1.1}
.ring-label{position:absolute;font-size:6px;color:#375A6F;font-weight:700}.l50{right:9px;top:25px}.l30{right:17px;top:50px}.l15{right:34px;top:70px}
.city-label{position:absolute;font-size:6px;color:#2B5569}.garching{left:51%;top:42px}.munich{left:48%;bottom:15px}
.zone-list>div{margin-bottom:7px;font-size:7px;color:#39576C}.zone-list b{display:block;color:#153A54;font-size:8px}.zone-list span{display:block;margin-left:13px}.zone-list i{float:left;width:9px;height:9px;border-radius:50%;margin:2px 5px 0 0}.z1{background:#087E83}.z2{background:#42C0CC}.z3{background:#A9E5E8}
.check{font-size:7px;color:#30556B;line-height:1.55}.check::first-letter{color:#087E83}
.budget-row{display:grid;grid-template-columns:28px 1fr auto;align-items:center;gap:7px;border:1px solid #E1E7EC;border-radius:7px;padding:8px;margin-bottom:7px;font-size:8px;color:#24445E}
.budget-row b{font-size:11px;color:#102A43}.budget-logo{font-size:18px;text-align:center;font-weight:800}.meta{color:#0064E0}.google{color:#DB4437}.reserve{color:#2B8BC8}
.budget-note{background:#FFF1D7;border-radius:7px;padding:8px;font-size:7px;color:#84561B;line-height:1.3}
.creative-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.creative-item{border:1px solid #DFE7ED;border-radius:7px;padding:6px;display:grid;grid-template-columns:84px 1fr;gap:7px;align-items:center}
.creative-item img{width:84px;height:54px;object-fit:cover;border-radius:5px}
.creative-item b{font-size:8px;color:#173A54;display:block;margin-bottom:2px}.creative-item span{display:block;font-size:7px;color:#38566D;line-height:1.25}.creative-item small{font-size:6.5px;color:#6A7F8E}
.rules-table td:first-child{white-space:nowrap}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px}.green{background:#1EA66A}.amber{background:#F1A20B}.red{background:#E04F3C}.blue{background:#2586D4}
@media(max-width:1050px){
  .action-panel,.hero-img{height:215px}
  .show-grid{grid-template-columns:repeat(2,1fr)}
  .kpi-grid{grid-template-columns:repeat(2,1fr)}
  .geo-wrap{grid-template-columns:1fr}
}
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
    sold_total = int(plan["sold"].dropna().sum()) if plan["sold"].notna().any() else None
    target_total = int(plan["target_today"].dropna().sum()) if plan["target_today"].notna().any() else None
    now = datetime.now(ZoneInfo("Europe/Berlin"))

    st.markdown(
        f"""
        <div class="topbar">
          <span class="top-chip">Resolution⌄</span>
          <span class="top-chip">▣ &nbsp;{now.strftime("%d %b %Y")}</span>
          <span class="top-chip">● &nbsp;ESO Supernova, Garching</span>
          <span class="top-avatar">MT</span><span class="top-chip">Management Team⌄</span>
        </div>
        <div class="main-title-row">
          <div>
            <h1>Resolution Ticket Sales Command Center</h1>
            <div class="main-sub">4 Tuesday screenings at <b>ESO Supernova</b> · <b>{capacity} total seats</b> · <b>€{int(cfg["marketing"]["total_budget_eur"])} maximum ad budget</b></div>
          </div>
          <div class="venue-id"><span class="venue-logo">◒</span><span><b>ESO Supernova</b><br>Planetarium & Visitor Centre<br>Garching, Germany</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    hero_left, hero_right = st.columns([1.05, 2.45], gap="small")
    with hero_left:
        st.markdown(
            f"""<div class="hero-img" style="background-image:url('{RESOLUTION_IMAGE}')">
              <div class="hero-film-title">RESOLUTION</div>
              <div class="hero-film-sub">A JOURNEY BEYOND</div>
              <div class="hero-film-venue">ESO SUPERNOVA<br>PLANETARIUM & VISITOR CENTRE<br>GARCHING, GERMANY</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with hero_right:
        st.markdown(
            f"""<div class="action-panel">
              <span class="reef-pill {status_class(decision["status"])}">{e(decision["status"])}</span>
              <h2>“What should we do today?”</h2>
              <div class="action-line">💡 &nbsp;{e(decision["headline"])}</div>
              <div class="action-detail">{e(decision["detail"])}</div>
              <div class="action-meta">
                <div><b>👥 &nbsp;Channel:</b>{e(decision["channel"])}</div>
                <div><b>📍 &nbsp;Where:</b>{e(decision["area"])}</div>
                <div><b>▣ &nbsp;Next check:</b>{e(decision["review"])}</div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

    kpis = [
        ("▣","Total seats",str(capacity)),
        ("◇","Tickets observed","Not live" if sold_total is None else str(sold_total)),
        ("↗","Healthy target today","Pre-launch" if target_total is None else str(target_total)),
        ("☷","Paid budget ceiling",f"€{int(cfg['marketing']['total_budget_eur'])}"),
    ]
    st.markdown(
        '<div class="kpi-grid">' + "".join(
            f'<div class="kpi"><div class="kpi-icon">{icon}</div><div><small>{label}</small><b>{value}</b></div></div>'
            for icon,label,value in kpis
        ) + '</div>',
        unsafe_allow_html=True,
    )

    screen_col, curve_col = st.columns([1.23, 1], gap="small")
    with screen_col:
        cards = "".join(screening_card(row) for _, row in plan.iterrows())
        st.markdown(
            f"""<div class="dash-card">
              <div class="screen-head"><div class="section-title">▣ &nbsp;Screening Control</div><a>View all screenings →</a></div>
              <div class="show-grid">{cards}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with curve_col:
        with st.container(border=True):
            st.markdown('<div class="section-title">↗ &nbsp;Healthy Booking Curve</div>', unsafe_allow_html=True)
            chart_col, mile_col = st.columns([1.65, .82], gap="small")
            with chart_col:
                st.plotly_chart(curve_chart(cfg), width="stretch", config={"displayModeBar": False})
            with mile_col:
                st.markdown('<div style="font-size:9px;font-weight:800;color:#173A54;margin-bottom:4px">Sales Milestones</div>' + milestones_html(cfg), unsafe_allow_html=True)

    plan_col, geo_col, budget_col = st.columns([1.48, 1.02, .86], gap="small")
    with plan_col:
        st.markdown('<div class="dash-card">' + operating_plan_html() + '</div>', unsafe_allow_html=True)
    with geo_col:
        st.markdown('<div class="dash-card">' + geography_html() + '</div>', unsafe_allow_html=True)
    with budget_col:
        st.markdown('<div class="dash-card">' + budget_html() + '</div>', unsafe_allow_html=True)

    creative_col, rules_col = st.columns([1.05, 1.1], gap="small")
    with creative_col:
        st.markdown('<div class="dash-card">' + creative_html() + '</div>', unsafe_allow_html=True)
    with rules_col:
        st.markdown('<div class="dash-card">' + rules_html() + '</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
