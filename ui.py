"""Shared presentation styles and navigation for the REEF launch dashboard."""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st


INK = "#102A43"
MUTED = "#526477"
TEAL = "#087E83"
BLUE = "#2B5D91"
AMBER = "#B56B15"

ESO_IMAGE = "https://supernova.eso.org/static/archives/images/screen/2018_04_14_Supernova_Night-CC.jpg"


def editing_enabled() -> bool:
    return os.environ.get("REEF_ENABLE_EDITING", "").strip() == "1"


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="reef-side-brand">
              <div class="reef-side-mark">≋</div>
              <div><b>REEF</b> <span>Distribution</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link("app.py", label="◆  Dashboard")
        st.page_link("pages/1_Sales_Plan.py", label="▥  Ticket Sales")
        st.page_link("pages/3_Marketing_Plan.py", label="◈  Campaign Plan")
        st.page_link("pages/2_Where_to_Advertise.py", label="●  Audiences")
        st.page_link("pages/4_Creatives.py", label="▣  Creatives")
        st.page_link("pages/6_Reports.py", label="▤  Reports")
        st.page_link("pages/9_Settings.py", label="⚙  Settings")
        st.markdown(
            f"""
            <div class="reef-side-photo" style="background-image:linear-gradient(180deg,rgba(9,35,58,.05),rgba(9,35,58,.88)),url('{ESO_IMAGE}')">
              <div class="reef-side-tagline">More people<br>to amazing places</div>
              <div class="reef-side-line"></div>
              <div class="reef-side-small"><b>REEF</b> Distribution</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_topbar() -> None:
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    st.html(
        f"""
        <div class="reef-global-topbar">
          <span class="reef-top-chip">Project · Resolution</span>
          <span class="reef-top-chip">▣ &nbsp;{now.strftime("%d %b %Y")}</span>
          <span class="reef-top-chip">● &nbsp;ESO Supernova, Garching</span>
          <span class="reef-top-avatar">MT</span>
          <span class="reef-top-chip">Management Team</span>
        </div>
        """
    )


def apply_theme() -> None:
    st.markdown(
        """
<style>
:root{
  --reef-ink:#102A43;
  --reef-muted:#526477;
  --reef-border:#DCE5EC;
  --reef-bg:#F6F9FB;
  --reef-teal:#087E83;
  --reef-navy:#0A2740;
}
html,body,[class*="css"]{font-family:Inter,Arial,sans-serif}
.stApp{background:var(--reef-bg)}
header[data-testid="stHeader"]{display:none!important}
[data-testid="stToolbar"]{display:none!important}
[data-testid="stDecoration"]{display:none!important}
[data-testid="stStatusWidget"]{display:none!important}
.block-container{
  max-width:1600px!important;
  padding:10px 18px 28px 18px!important;
}
.reef-global-topbar{
  height:34px;
  margin:-10px -18px 8px;
  padding:0 18px;
  border-bottom:1px solid #E1E8EE;
  background:#fff;
  display:flex;
  justify-content:flex-end;
  align-items:center;
  gap:7px;
}
.reef-top-chip{
  border:1px solid #E1E8EE;
  background:#FBFCFD;
  border-radius:7px;
  padding:5px 9px;
  font-size:9px;
  color:#24425D;
  white-space:nowrap;
}
.reef-top-avatar{
  width:23px;height:23px;border-radius:50%;
  display:inline-grid;place-items:center;
  background:#11344E;color:white;
  font-size:8px;font-weight:800;
}
[data-testid="stSidebar"]{
  background:#08263F!important;
  border-right:0!important;
  width:190px!important;
  min-width:190px!important;
}
[data-testid="stSidebarContent"]{padding:0!important}
[data-testid="stSidebarNav"]{display:none!important}
[data-testid="collapsedControl"]{display:none!important}
[data-testid="stSidebar"] .stPageLink{margin:2px 10px!important}
[data-testid="stSidebar"] .stPageLink a{
  min-height:38px!important;
  border-radius:7px!important;
  padding:8px 10px!important;
  color:#D4E0EA!important;
  font-size:11px!important;
  font-weight:560!important;
  letter-spacing:.005em;
  gap:7px!important;
  text-decoration:none!important;
}
[data-testid="stSidebar"] .stPageLink a p,
[data-testid="stSidebar"] .stPageLink a span,
[data-testid="stSidebar"] .stPageLink a div{
  color:#D4E0EA!important;
}
[data-testid="stSidebar"] .stPageLink a svg{
  color:#D4E0EA!important;
  fill:currentColor!important;
}
[data-testid="stSidebar"] .stPageLink a:hover{
  background:#113C5C!important;
  color:white!important;
}
[data-testid="stSidebar"] .stPageLink a[aria-current="page"]{
  background:#0E4D70!important;
  color:#55D4E1!important;
}
[data-testid="stSidebar"] .stPageLink a[aria-current="page"] p,
[data-testid="stSidebar"] .stPageLink a[aria-current="page"] span,
[data-testid="stSidebar"] .stPageLink a[aria-current="page"] div,
[data-testid="stSidebar"] .stPageLink a[aria-current="page"] svg{
  color:#55D4E1!important;
}
[data-testid="stSidebar"] .stPageLink svg{width:16px!important;height:16px!important}
.reef-side-brand{
  min-height:64px;
  padding:18px 15px 15px 15px;
  border-bottom:1px solid rgba(255,255,255,.10);
  display:flex;align-items:center;gap:7px;
  color:white;font-size:17px;letter-spacing:-.02em;
}
.reef-side-brand span{font-weight:400;color:#D7E1EA;font-size:13px}
.reef-side-mark{font-size:27px;line-height:1;color:#EAF7FA;letter-spacing:-.08em}
.reef-side-photo{
  min-height:380px;
  height:calc(100vh - 410px);
  margin-top:28px;
  background-position:center;
  background-size:cover;
  display:flex;
  flex-direction:column;
  justify-content:flex-end;
  padding:16px;
  color:white;
}
.reef-side-tagline{font-size:15px;line-height:1.34;color:#E8F2F8;margin-bottom:28px}
.reef-side-line{width:24px;border-top:1px solid #5BB6C2;margin-bottom:13px}
.reef-side-small{font-size:13px;color:#DDE8EF}
h1,h2,h3,h4{color:var(--reef-ink);letter-spacing:-.025em}
h1{font-size:25px!important;line-height:1.08!important;margin:0!important;font-weight:780!important}
h2{font-size:16px!important;line-height:1.15!important;margin:0 0 8px!important;font-weight:760!important}
h3{font-size:14px!important;margin:0 0 7px!important;font-weight:740!important}
p,li{line-height:1.38;font-size:12px}
[data-testid="stMarkdownContainer"] p{margin-bottom:.35rem}
[data-testid="stVerticalBlock"]{gap:.55rem!important}
[data-testid="stHorizontalBlock"]{gap:.65rem!important}
[data-testid="stMetric"]{
  background:#fff!important;
  border:1px solid var(--reef-border)!important;
  border-radius:10px!important;
  min-height:68px!important;
  padding:11px 14px!important;
  box-shadow:none!important;
}
[data-testid="stMetricLabel"]{font-size:11px!important;color:#3F566A!important}
[data-testid="stMetricValue"]{font-size:20px!important;color:var(--reef-ink)!important;font-weight:760!important}
[data-testid="stPlotlyChart"]{
  background:white!important;
  border:0!important;
  border-radius:8px!important;
  overflow:hidden;
}
[data-testid="stDataFrame"]{
  border:1px solid var(--reef-border)!important;
  border-radius:8px!important;
  overflow:hidden!important;
  font-size:11px!important;
}
[data-testid="stVerticalBlockBorderWrapper"]{
  background:white!important;
  border:1px solid var(--reef-border)!important;
  border-radius:10px!important;
  box-shadow:none!important;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div{padding:10px 11px!important}
.reef-eyebrow{
  color:#087E83;
  font-size:10px;
  font-weight:800;
  letter-spacing:.11em;
  text-transform:uppercase;
  margin-bottom:5px;
}
.reef-pill{
  display:inline-block;padding:3px 8px;border-radius:999px;
  font-size:9px;font-weight:800;letter-spacing:.02em;
  background:#E4F3F5;color:#166B78;
}
.reef-pill-green{background:#E5F6ED!important;color:#167249!important}
.reef-pill-amber{background:#FFF2D9!important;color:#9A5B00!important}
.reef-pill-red{background:#FDE9E6!important;color:#B13D2D!important}
.reef-pill-blue{background:#DDF0F5!important;color:#17677E!important}
.reef-pill-gray{background:#EDF2F5!important;color:#5A6A79!important}
.reef-note{font-size:10px;color:var(--reef-muted);line-height:1.35}
.reef-label{font-size:9px;color:var(--reef-muted);text-transform:uppercase;letter-spacing:.07em;font-weight:800}
.reef-number{font-size:22px;color:var(--reef-ink);font-weight:780}
.reef-cta{
  background:#E7F5F1;border-left:3px solid var(--reef-teal);
  border-radius:7px;padding:10px 12px;color:#164A4D;font-size:11px;
}
.reef-cta strong{color:#0A5D62}
.reef-card,.panel,.map-card{
  background:#fff!important;
  color:#102A43!important;
  border:1px solid #DCE5EC!important;
  border-radius:10px!important;
  padding:14px!important;
  box-shadow:none!important;
  height:100%;
  box-sizing:border-box;
}
.reef-card h3,.panel h3,.map-card h3{margin:3px 0 7px!important;font-size:13px!important}
.reef-card p,.panel p,.map-card p{font-size:10px!important;color:#526477!important;margin:.3rem 0}
.reef-hero,.hero,.hero-map{
  background:linear-gradient(120deg,#102A42,#174D5C)!important;
  border:0!important;
  border-radius:12px!important;
  color:white!important;
  padding:18px 20px!important;
  margin-bottom:10px!important;
}
.reef-hero h1,.hero h1,.hero-map h1{color:white!important;font-size:22px!important}
.reef-hero p,.hero p,.hero-map p{color:#D6E7EE!important;font-size:10px!important;margin:3px 0 0}
.badge{display:inline-block;background:#E6F4F2!important;color:#087E83!important;border:1px solid #BCE0DB!important;border-radius:999px;padding:3px 7px;font-size:8px}
.small,.small-muted{font-size:9px!important;color:#6A7E8E!important}
@media(max-width:900px){
  [data-testid="stSidebar"]{width:150px!important;min-width:150px!important}
  .block-container{padding:8px 10px 22px 10px!important}
  .reef-side-photo{display:none}
}
</style>
        """,
        unsafe_allow_html=True,
    )
    render_sidebar()
    render_topbar()


def page_intro(section: str, title: str, description: str) -> None:
    st.markdown(f'<div class="reef-eyebrow">{section}</div>', unsafe_allow_html=True)
    st.title(title)
    st.caption(description)


def select_market(label: str = "Target market city") -> dict:
    from market_context import custom_market, default_market_key, market_catalog

    catalog = market_catalog()
    options = list(catalog.keys()) + ["Custom city"]
    current = st.session_state.get("reef_market_key", default_market_key())
    if current not in options:
        current = default_market_key()
    picked = st.selectbox(label, options, index=options.index(current), key="reef_market_picker")
    st.session_state["reef_market_key"] = picked

    if picked != "Custom city":
        market = catalog[picked]
        st.session_state["reef_market_context"] = market
        return market

    custom_name = st.text_input("Custom city name", value=st.session_state.get("reef_custom_city_name", "Custom city"), key="reef_custom_city_name_input")
    c1, c2, c3 = st.columns(3)
    lat = c1.number_input("Latitude", value=float(st.session_state.get("reef_custom_city_lat", 48.1372)), format="%.6f", key="reef_custom_city_lat_input")
    lon = c2.number_input("Longitude", value=float(st.session_state.get("reef_custom_city_lon", 11.5756)), format="%.6f", key="reef_custom_city_lon_input")
    radius = c3.number_input("Test radius (km)", min_value=0.5, max_value=20.0, value=float(st.session_state.get("reef_custom_city_radius", 2.5)), step=0.5, key="reef_custom_city_radius_input")
    st.session_state["reef_custom_city_name"] = custom_name
    st.session_state["reef_custom_city_lat"] = lat
    st.session_state["reef_custom_city_lon"] = lon
    st.session_state["reef_custom_city_radius"] = radius
    market = custom_market(custom_name, lat, lon, radius)
    st.session_state["reef_market_context"] = market
    return market


def current_market() -> dict:
    from market_context import get_market
    return st.session_state.get("reef_market_context") or get_market(st.session_state.get("reef_market_key"))
