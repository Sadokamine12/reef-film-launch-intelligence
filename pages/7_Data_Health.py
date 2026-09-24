from __future__ import annotations

import pandas as pd
import streamlit as st

from data_health import health_frame, health_summary
from experiment_protocol import attribution_requirements
from ui import apply_theme, page_intro

st.set_page_config(page_title="Data Health", page_icon="🩺", layout="wide")
apply_theme()
page_intro("Operational readiness", "Data Health", "What is ready, what is missing, and what limits the forecast today.")

summary = health_summary()
c1,c2,c3,c4 = st.columns(4)
c1.metric("Blocking issues", summary["blocking"])
c2.metric("Warnings", summary["warnings"])
c3.metric("Valid ESO snapshots", summary["coverage"]["rows"])
c4.metric("Attribution level", summary["attribution"]["level"])

frame = health_frame()
frame["Status"] = frame.apply(lambda r: "OK" if r["ok"] else ("WARNING" if r["level"]=="warning" else "BLOCKING"), axis=1)
st.subheader("What needs attention")
active = frame.loc[~frame["ok"], ["Status", "check", "detail"]]
if active.empty:
    st.success("All checks pass.")
else:
    st.dataframe(active, width="stretch", hide_index=True)
with st.expander("Show every project doctor check"):
    st.dataframe(frame[["Status","check","detail"]], width="stretch", hide_index=True)

with st.expander("Understand attribution levels A–E"):
    st.dataframe(attribution_requirements(), width="stretch", hide_index=True)

st.subheader("Methodology boundaries")
st.markdown("""
- **ESO empirical baseline** describes how comparable ESO shows sell over lead time. It is not proof that Resolution will behave identically.
- **ESO demand ML** is an adjustment model. It is not used operationally until grouped-by-show validation passes.
- **Engagement ML** can learn clicks/video/landing-page response before ticket attribution exists.
- **Ticket-lift ML** only trains on labels with an explicit verified source. The software will not invent purchase attribution from clicks.
- **Total seat-curve lift** can measure whether the campaign likely changed overall sales velocity, but cannot identify the exact winning geography if multiple ad cells run simultaneously without purchase-source tracking.
- **Budget optimization** becomes operational only when ticket-lift validation passes. Before then it is an experiment-priority scenario.
""")
