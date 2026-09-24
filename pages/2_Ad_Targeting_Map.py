from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ad_targeting_map import (
    planned_zones,
    load_campaign_history,
    measured_area_performance,
    join_measured_to_zones,
    u6_path_frame,
)
from ui import apply_theme

st.set_page_config(page_title="Resolution Ad Targeting Map", page_icon="🗺️", layout="wide")

st.markdown(
    """
<style>
.block-container{padding-top:1rem;max-width:1550px}
.hero-map{padding:22px 26px;border-radius:22px;background:linear-gradient(120deg,#0c1118,#122235 58%,#14333a);border:1px solid #29384a;margin-bottom:16px}
.hero-map h1{font-size:2.1rem;margin:0 0 7px 0}.hero-map p{margin:0;color:#b8c5d6}
.map-card{border:1px solid #29384a;background:#101720;border-radius:16px;padding:15px 17px;height:100%}
.small-muted{color:#94a3b8;font-size:.87rem}
[data-testid="stMetric"]{background:#101720;border:1px solid #29384a;padding:14px;border-radius:14px}
[data-testid="stPlotlyChart"]{border:1px solid #29384a;border-radius:18px;overflow:hidden;background:#0b1118}
</style>
""",
    unsafe_allow_html=True,
)
apply_theme()

from project_config import load_config
from campaign_lab import attribution_readiness

cfg = load_config()
marketing_cfg = cfg.get("marketing", {})
attribution = attribution_readiness()

st.markdown(
    """
<div class="hero-map">
  <h1>Where to market</h1>
  <p>Three balanced geography tests near ESO and along the U6 corridor · EUR 90 first wave</p>
</div>
""",
    unsafe_allow_html=True,
)

total_budget = int(marketing_cfg.get("total_budget_eur", 500))
validation_budget = int(marketing_cfg.get("experiment_budget_eur", 240))
search_budget = 40
with st.expander("Map display options"):
    show_u6 = st.toggle("Show U6 corridor", value=True)
    show_labels = st.toggle("Show zone labels", value=True)
    basemap_name = st.selectbox(
        "Map background",
        ["OpenStreetMap", "Carto light", "Carto dark", "No tiles (fallback)"],
        index=0,
        help="If your network blocks one tile provider, switch to another. 'No tiles' still shows all campaign zones.",
    )

zones, meta = planned_zones(total_budget, validation_budget, search_budget)
history = load_campaign_history()
measured = measured_area_performance(history)
zones = join_measured_to_zones(zones, measured)
measured_ready = not measured.empty and measured.get("observations", pd.Series(dtype=float)).sum() >= 4

# Stable role colours. Plotly wants rgba strings.
ROLE_COLORS = {
    "Primary": (38, 196, 166),
    "Local": (72, 145, 245),
    "U6": (139, 92, 246),
    "Culture": (245, 158, 66),
}

k1, k2, k3 = st.columns(3)
k1.metric("First geography test", f"EUR {meta['geo_budget']:.0f}")
k2.metric("Balanced cells", "3 areas × 2 creatives")
k3.metric("Held for later decisions", f"EUR {meta['total_budget']-meta['geo_budget']:.0f}")
st.caption("Area colours show measured tracked-purchase performance when reliable rows exist. Until then they show test geography, not a success probability.")

if measured_ready:
    st.success("Measured ticket-attribution data exists. The zone cards include verified performance where available.")
else:
    st.info("Pre-campaign mode: these circles are **experimental test zones**, not proven winners. Exact ticket-level geo learning requires verified purchase attribution.")
    if attribution.get("verified_ticket_rows", 0) == 0:
        st.caption("Attribution prerequisite: ESO conversion/source reporting, unique promo codes, or another verified purchase source. With seat counts only, we can measure total lift but not honestly assign each sale to a geography.")


def circle_points(lat: float, lon: float, radius_km: float, n: int = 72):
    """Approximate a geodesic circle around a map point."""
    earth_km = 6371.0088
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    angular = radius_km / earth_km
    lats, lons = [], []
    for i in range(n + 1):
        bearing = 2 * math.pi * i / n
        lat2 = math.asin(
            math.sin(lat1) * math.cos(angular)
            + math.cos(lat1) * math.sin(angular) * math.cos(bearing)
        )
        lon2 = lon1 + math.atan2(
            math.sin(bearing) * math.sin(angular) * math.cos(lat1),
            math.cos(angular) - math.sin(lat1) * math.sin(lat2),
        )
        lats.append(math.degrees(lat2))
        lons.append(math.degrees(lon2))
    return lats, lons


MAP_STYLE = {
    "OpenStreetMap": "open-street-map",
    "Carto light": "carto-positron",
    "Carto dark": "carto-darkmatter",
    "No tiles (fallback)": "white-bg",
}[basemap_name]

left, right = st.columns([1.7, 1])

with left:
    st.subheader("Where to show the ads")

    fig = go.Figure()

    # U6 accessibility corridor (planning aid, not a targeting polygon).
    if show_u6:
        u6 = u6_path_frame()
        fig.add_trace(
            go.Scattermap(
                lat=u6["lat"],
                lon=u6["lon"],
                mode="lines+markers",
                name="U6 access corridor",
                line=dict(width=5, color="rgba(139,92,246,0.85)"),
                marker=dict(size=8, color="white"),
                text=u6["name"],
                hovertemplate="<b>%{text}</b><br>U6 accessibility corridor<extra></extra>",
            )
        )

    # Target radius polygons + centre markers.
    for _, r in zones.loc[zones["budget_eur"].gt(0)].sort_values("priority_score", ascending=False).iterrows():
        rgb = ROLE_COLORS.get(r["role"], (90, 150, 220))
        if pd.notna(r.get("measured_score", pd.NA)):
            rgb = (38, 196, 166) if float(r["measured_score"]) >= 75 else (245, 158, 66) if float(r["measured_score"]) >= 50 else (239, 104, 104)
        lats, lons = circle_points(float(r["lat"]), float(r["lon"]), float(r["radius_km"]))
        hover = (
            f"<b>{r['area']}</b><br>"
            f"Radius: {float(r['radius_km']):.1f} km<br>"
            f"Initial geo budget: €{int(r['budget_eur'])}<br>"
            f"Priority: {int(round(r['display_score']))}/100<br>"
            f"Age: {r['age']}<br>"
            f"{r['why']}<br>"
            f"<i>{r['score_basis']}</i>"
        )

        fig.add_trace(
            go.Scattermap(
                lat=lats,
                lon=lons,
                mode="lines",
                fill="toself",
                fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.16)",
                line=dict(width=2, color=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.85)"),
                name=r["area"],
                hoverinfo="skip",
                showlegend=False,
            )
        )

        label_text = f"{r['area']}<br>€{int(r['budget_eur'])}" if show_labels else ""
        fig.add_trace(
            go.Scattermap(
                lat=[float(r["lat"])],
                lon=[float(r["lon"])],
                mode="markers+text" if show_labels else "markers",
                marker=dict(size=16 if r["role"] == "Primary" else 13, color=f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"),
                text=[label_text],
                textposition="top center",
                textfont=dict(size=12, color="white" if basemap_name in {"Carto dark", "No tiles (fallback)"} else "#111827"),
                customdata=[[r["area"], r["radius_km"], r["budget_eur"], r["display_score"], r["age"], r["why"], r["score_basis"]]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Radius: %{customdata[1]:.1f} km<br>"
                    "Initial geo budget: €%{customdata[2]:.0f}<br>"
                    "Priority: %{customdata[3]:.0f}/100<br>"
                    "Age: %{customdata[4]}<br>"
                    "%{customdata[5]}<br>"
                    "<i>%{customdata[6]}</i><extra></extra>"
                ),
                name=r["area"],
                showlegend=False,
            )
        )

    # Exact ESO venue marker above all zones.
    fig.add_trace(
        go.Scattermap(
            lat=[48.259828],
            lon=[11.670136],
            mode="markers+text",
            marker=dict(size=20, color="white"),
            text=["★ ESO Supernova"],
            textposition="bottom center",
            textfont=dict(size=13, color="white" if basemap_name in {"Carto dark", "No tiles (fallback)"} else "#111827"),
            hovertemplate="<b>ESO Supernova</b><br>Karl-Schwarzschild-Str. 2, Garching<br>Campaign destination / screening venue<extra></extra>",
            name="ESO Supernova",
            showlegend=False,
        )
    )

    fig.update_layout(
        map=dict(
            style=MAP_STYLE,
            center=dict(lat=48.215, lon=11.625),
            zoom=10.15,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=650,
        showlegend=False,
        paper_bgcolor="#0b1118",
        plot_bgcolor="#0b1118",
        uirevision="resolution-map-v8-8",
    )

    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
    st.caption("The circles are proposed paid-ad test radii. The U6 line is an accessibility signal, not a Meta targeting object. If tiles ever appear blank, choose another map background in the sidebar.")

with right:
    st.subheader("Exact first test")
    for _, r in zones.loc[zones["budget_eur"].gt(0)].sort_values("priority_score", ascending=False).iterrows():
        extra = ""
        if pd.notna(r.get("ticket_cpa", pd.NA)):
            extra = f"<br><b>Measured CPA:</b> €{float(r['ticket_cpa']):.2f} • {int(r.get('tickets', 0))} attributed tickets"
        st.markdown(
            f"""
        <div class="map-card">
          <b>{r['area']}</b><br>
          <span class="small-muted">{r['role']} • {r['radius_km']:.1f} km radius • age {r['age']}</span><br><br>
          <b>€{int(r['budget_eur'])}</b> initial geo spend<br>
          Priority <b>{int(round(r['display_score']))}/100</b>{extra}<br>
          <span class="small-muted">{r['why']}<br>Creative: {r['creative']}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )
        st.write("")

st.divider()

# Clear executive allocation summary.
st.subheader("€500 campaign allocation")
allocation = pd.DataFrame(
    [
        ["Meta — first-wave zones", meta["geo_budget"], "Three geographies × two creatives"],
        ["Later age and retargeting tests", meta["later_tests"], "Conditional learning spend"],
        ["Google Search", meta["search_budget"], "High-intent searches, Munich + Garching"],
        ["Winner reserve", meta["scale_reserve"], "Move only to the measured best geo/audience/creative"],
    ],
    columns=["Bucket", "Budget €", "Purpose"],
)
st.dataframe(allocation, width="stretch", hide_index=True)

st.subheader("Ad sets to create")
adsets = zones.loc[zones["budget_eur"].gt(0), ["area", "radius_km", "age", "budget_eur", "display_score", "creative", "why"]].copy()
adsets.columns = ["Ad set / map zone", "Radius km", "Age", "Initial €", "Priority", "Creative angle", "Why test here"]
st.dataframe(adsets.sort_values("Priority", ascending=False), width="stretch", hide_index=True)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        """
    <div class="map-card"><b>1 • Keep geo tests separate</b><br><br>
    One zone = one ad set. Never combine Garching, Studentenstadt and Schwabing in the first test, otherwise the model cannot learn which geography actually performs.<br><br>
    <span class="small-muted">Use the same creative and objective when comparing geographies.</span></div>
    """,
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f"""
    <div class="map-card"><b>2 • Search is separate</b><br><br>
    Keep <b>€{meta['search_budget']:.0f}</b> for high-intent Google Search. It should not be interpreted as one of the circles on the map.<br><br>
    <span class="small-muted">Track the same destination URL/UTM structure so search can be compared against Meta.</span></div>
    """,
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f"""
    <div class="map-card"><b>3 • Protect the reserve</b><br><br>
    Hold <b>€{meta['scale_reserve']:.0f}</b> until the first data shows a winner. Then concentrate it instead of spreading it equally.<br><br>
    <span class="small-muted">This is where the campaign changes from prediction to evidence-based scaling.</span></div>
    """,
        unsafe_allow_html=True,
    )

if not measured.empty:
    st.subheader("Measured geography performance")
    st.dataframe(measured, width="stretch", hide_index=True)
else:
    st.caption("No measured geo performance yet. Add campaign rows with `area`, `spend_eur` and `tickets_attributed` to `data/campaign_history.csv`. The map will then add real CPA/ticket performance automatically.")
