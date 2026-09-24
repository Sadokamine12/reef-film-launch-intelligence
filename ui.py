"""Shared presentation styles for the REEF decision dashboard."""
from __future__ import annotations

import os
import streamlit as st


INK = "#14283D"
MUTED = "#526477"
TEAL = "#087E83"
BLUE = "#2B5D91"
AMBER = "#B56B15"


def editing_enabled() -> bool:
    """Allow local data changes only when the trusted launcher opts in."""
    return os.environ.get("REEF_ENABLE_EDITING", "").strip() == "1"


def apply_theme() -> None:
    st.markdown("""
<style>
/* Page frame and navigation */
.block-container{max-width:1340px;padding-top:2.3rem;padding-bottom:5rem}
[data-testid="stSidebar"]{background:#F1F5F8;border-right:1px solid #DFE7EC}
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding-top:1.4rem}
[data-testid="stSidebarNav"]{font-size:.94rem}
[data-testid="stSidebarNav"] li{margin:4px 0}
[data-testid="stSidebarNav"] a{border-radius:8px}
[data-testid="stToolbar"]{display:none!important}
h1,h2,h3{color:#14283D;letter-spacing:-.025em}
h1{font-weight:740!important;line-height:1.08!important}
h2{font-weight:680!important;margin-top:2rem!important}
h3{font-weight:640!important}
p,li{line-height:1.5}
/* Native widgets and charts */
[data-testid="stMetric"]{background:#FFFFFF!important;border:1px solid #DBE5EB!important;padding:17px 19px!important;border-radius:14px!important;box-shadow:0 5px 18px rgba(18,43,66,.04)!important;min-height:112px}
[data-testid="stMetricLabel"]{color:#526477!important;font-size:.87rem!important}
[data-testid="stMetricValue"]{color:#14283D!important;font-size:1.65rem!important;line-height:1.12!important;white-space:normal!important;overflow:visible!important}
[data-testid="stMetricDelta"]{color:#526477!important;font-size:.8rem!important}
[data-testid="stMetricDelta"] svg{display:none}
[data-testid="stPlotlyChart"]{background:#FFFFFF!important;border:1px solid #DBE5EB!important;border-radius:14px!important;overflow:hidden}
[data-testid="stDataFrame"]{border:1px solid #DBE5EB;border-radius:12px;overflow:hidden}
/* Consistent panel styles on legacy drill-down pages */
.panel,.map-card{background:#FFFFFF!important;color:#14283D!important;border:1px solid #DBE5EB!important;border-radius:14px!important;box-shadow:0 5px 18px rgba(18,43,66,.04)!important}
.panel b,.map-card b{color:#14283D!important}
.small,.small-muted{color:#526477!important}
.hero,.hero-map{background:linear-gradient(120deg,#102A42,#174862)!important;border:0!important;border-radius:17px!important;color:#FFFFFF!important}
.hero h1,.hero-map h1{color:#FFFFFF!important}
.hero p,.hero-map p{color:#D8E8F0!important}
.badge{background:#E8F4F2!important;color:#087E83!important;border-color:#BCE0DB!important}
/* New executive components */
.reef-hero{padding:32px 36px;background:linear-gradient(120deg,#102A42,#174D5C);border-radius:20px;color:white;margin-bottom:24px}
.reef-eyebrow{color:#87D8D4;font-size:.79rem;font-weight:750;letter-spacing:.13em;text-transform:uppercase;margin-bottom:10px}
.reef-hero h1{color:white!important;font-size:2.45rem!important;margin:.1rem 0 .55rem}
.reef-hero p{color:#D6E7EE;font-size:1rem;margin:0}
.reef-card{background:white;border:1px solid #DBE5EB;border-radius:16px;padding:24px;box-shadow:0 5px 18px rgba(18,43,66,.04);height:100%;color:#14283D}
.reef-card h3{margin:4px 0 12px!important;font-size:1.16rem}
.reef-card p{color:#526477;margin:.4rem 0}
.reef-label{color:#526477;font-size:.78rem;font-weight:750;letter-spacing:.09em;text-transform:uppercase}
.reef-number{font-size:2.45rem;font-weight:760;line-height:1.05;color:#14283D;letter-spacing:-.04em;margin:12px 0 6px}
.reef-note{font-size:.85rem;color:#526477}
.reef-pill{display:inline-block;padding:5px 10px;border-radius:100px;background:#E8F4F2;color:#087E83;font-size:.77rem;font-weight:740}
.reef-pill-amber{background:#FFF2DD;color:#8C580D}
.reef-pill-red{background:#FCEBE8;color:#A84334}
.reef-cta{background:#E8F4F2;border-left:4px solid #087E83;border-radius:12px;padding:19px 22px;color:#173A43;margin:10px 0 21px}
.reef-cta strong{color:#0A5D62}
.reef-divider{border-top:1px solid #DBE5EB;margin:1.5rem 0}
</style>
""", unsafe_allow_html=True)


def page_intro(section: str, title: str, description: str) -> None:
    st.markdown(f'<div class="reef-eyebrow" style="color:#087E83">{section}</div>', unsafe_allow_html=True)
    st.title(title)
    st.caption(description)
