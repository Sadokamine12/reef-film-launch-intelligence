"""Shared presentation styles and navigation for the REEF launch dashboard."""
from __future__ import annotations

import os
import streamlit as st


INK = "#102A43"
MUTED = "#526477"
TEAL = "#087E83"
BLUE = "#2B5D91"
AMBER = "#B56B15"

ESO_IMAGE = "https://supernova.eso.org/static/archives/images/screen/PANO0003-CC.jpg"


def editing_enabled() -> bool:
    return os.environ.get("REEF_ENABLE_EDITING", "").strip() == "1"


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="reef-side-brand">
              <div class="reef-side-mark">⌁</div>
              <div><b>REEF</b> <span>Distribution</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link("app.py", label="Dashboard", icon="🏠")
        st.page_link("pages/1_Sales_Plan.py", label="Ticket Sales", icon="📊")
        st.page_link("pages/3_Marketing_Plan.py", label="Campaign Plan", icon="📣")
        st.page_link("pages/2_Where_to_Advertise.py", label="Audiences", icon="👥")
        st.page_link("pages/3_Marketing_Plan.py", label="Creatives", icon="🖼️")
        st.page_link("pages/5_Campaign_Data.py", label="Reports", icon="📄")
        st.page_link("pages/7_Data_Health.py", label="Settings", icon="⚙️")
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
  max-width:none!important;
  padding:10px 18px 28px 18px!important;
}
[data-testid="stSidebar"]{
  background:#08263F!important;
  border-right:0!important;
  width:176px!important;
  min-width:176px!important;
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
  font-size:12px!important;
  gap:8px!important;
}
[data-testid="stSidebar"] .stPageLink a:hover{
  background:#113C5C!important;
  color:white!important;
}
[data-testid="stSidebar"] .stPageLink a[aria-current="page"]{
  background:#0E4D70!important;
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
.reef-side-brand span{font-weight:400;color:#D7E1EA;font-size:14px}
.reef-side-mark{font-size:25px;line-height:1;color:#EAF7FA;transform:rotate(-20deg)}
.reef-side-photo{
  min-height:360px;
  margin-top:38px;
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
