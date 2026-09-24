from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from model_quality import eso_coverage, current_eso_model, quality_label, next_data_actions, training_history, load_status
from training_engine import run_all_training
from ui import apply_theme, editing_enabled, page_intro

st.set_page_config(page_title="Model Quality", page_icon="📈", layout="wide")
apply_theme()
page_intro("Reliability", "Model Quality", "Validation error, data coverage, and the rule that decides which forecast can be used.")

coverage = eso_coverage()
model = current_eso_model()
label,note = quality_label(model, coverage["coverage_score"])
status = load_status()

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Baseline quality", label)
c2.metric("Canonical snapshots", coverage["rows"])
c3.metric("Unique shows", coverage["unique_shows"])
c4.metric("Repeated shows", coverage["repeated_shows"])
c5.metric("Grouped CV MAE", "—" if model.get("mae") is None else f"{float(model['mae']):.1f} pp")
c6.metric("Grouped CV R²", "—" if model.get("r2") is None else f"{float(model['r2']):.2f}")
st.info(note)

if model:
    st.subheader("Which baseline is used?")
    st.info("The empirical ESO curve is active. The learned demand model is held back because its grouped validation error is above the configured 12-point gate.")
    card = pd.DataFrame([{
        "Status":model.get("status"), "Operational":model.get("operational"), "Rows":model.get("rows"),
        "Validation":model.get("validation_mode"), "ML MAE":model.get("mae"), "ML R²":model.get("r2"),
        "Empirical benchmark MAE":model.get("benchmark_mae"), "Empirical benchmark R²":model.get("benchmark_r2"),
        "Target":model.get("target"),
    }])
    with st.expander("Detailed model metrics"):
        st.dataframe(card, width="stretch", hide_index=True)
    if not model.get("operational", False):
        st.warning("The learned ESO adjustment is **not used operationally**. The dashboard falls back to the empirical monotonic sales curve until the ML model beats the configured quality gate and empirical benchmark.")

st.subheader("Lead-time coverage")
if coverage["buckets"].empty:
    st.warning("No baseline data.")
else:
    fig = px.bar(coverage["buckets"], x="lead_window", y="snapshots", text="snapshots")
    fig.update_layout(height=360, xaxis_title="Lead-time window", yaxis_title="Snapshots")
    st.plotly_chart(fig, width="stretch")

hist = training_history()
if not hist.empty:
    eso = hist[hist["model"].astype(str).str.startswith("ESO demand")].copy()
    if not eso.empty:
        eso["trained_at_utc"] = pd.to_datetime(eso["trained_at_utc"], errors="coerce")
        for c in ["rows","mae","r2","benchmark_mae"]:
            if c in eso.columns:
                eso[c] = pd.to_numeric(eso[c], errors="coerce")
        st.subheader("Validation history")
        left,right = st.columns(2)
        with left:
            plot = eso.dropna(subset=["mae"])
            if not plot.empty:
                fig = px.line(plot, x="trained_at_utc", y="mae", markers=True, title="Grouped CV MAE")
                if "benchmark_mae" in plot.columns:
                    fig.add_scatter(x=plot["trained_at_utc"], y=plot["benchmark_mae"], mode="lines+markers", name="Empirical benchmark MAE")
                st.plotly_chart(fig, width="stretch")
        with right:
            plot = eso.dropna(subset=["r2"])
            if not plot.empty:
                fig = px.line(plot, x="trained_at_utc", y="r2", markers=True, title="Grouped CV R²")
                fig.add_hline(y=0, line_dash="dot")
                st.plotly_chart(fig, width="stretch")

st.subheader("Next data actions")
for x in next_data_actions(coverage, model):
    st.write("• " + x)

if editing_enabled() and st.button("Retrain now", type="primary"):
    results = run_all_training()
    st.success("Retraining completed. Reload the page to refresh the charts.")
    for r in results:
        st.write(f"{r.name}: {r.status}, rows={r.rows}, MAE={r.mae}, R²={r.r2}, operational={r.operational}")
