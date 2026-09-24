"""Presales evidence and live Resolution pace."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from advanced_ml import empirical_baseline, load_resolution_sales
from project_config import load_config
from ui import apply_theme, page_intro

st.set_page_config(page_title="Sales Forecast", page_icon="📊", layout="wide")
apply_theme()
page_intro("Demand evidence", "Sales Forecast", "Actual ESO inventory, the empirical fit, and Resolution sales pace when tickets go live.")
cfg = load_config()
curve, stats, comparable = empirical_baseline()
resolution = load_resolution_sales()

if curve.empty:
    st.warning("No valid ESO booking observations yet. Run DAILY_UPDATE.bat.")
else:
    st.metric("Comparable evidence", f"{stats['unique_shows']} shows", f"{stats['rows']} booking snapshots")
    st.warning(f"Nearest comparable observation is {stats['min_days_to_event']} days before show. Values closer to showtime are extrapolated from the observed range and have very low confidence.")
    fig = go.Figure()
    x = curve["days_to_event"]
    fig.add_trace(go.Scatter(x=x, y=curve["high_sold_pct"] * 1.09, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=curve["low_sold_pct"] * 1.09, fill="tonexty", line=dict(width=0), name="Comparable uncertainty"))
    fig.add_trace(go.Scatter(x=x, y=curve["base_sold_pct"] * 1.09, name="ESO fitted estimate", line=dict(color="#65b9d6", width=3)))
    fig.add_trace(go.Scatter(x=comparable["days_to_event"], y=comparable["tickets_sold_so_far"], mode="markers", name="ESO actual", text=comparable["programme_title"], hovertemplate="%{text}<br>%{x} days before<br>%{y} seats sold<extra></extra>"))
    if not resolution.empty:
        actual = resolution[resolution["status"].astype(str).str.startswith("ok")].copy()
        actual = actual.dropna(subset=["days_to_event", "tickets_sold"])
        for show_date, group in actual.groupby("show_date"):
            group = group.sort_values("days_to_event", ascending=False)
            fig.add_trace(go.Scatter(x=group["days_to_event"], y=group["tickets_sold"], mode="lines+markers", name=f"Resolution actual {str(show_date)[:10]}"))
    fig.update_layout(height=500, xaxis_title="Days before show", yaxis_title="Tickets sold per screening", hovermode="closest")
    fig.update_xaxes(autorange="reversed")
    fig.update_yaxes(range=[0, cfg["venue"]["capacity_per_show"]])
    st.plotly_chart(fig, width="stretch")

if resolution.empty:
    st.info("No Resolution booking observations yet. The four booking IDs must become public before actual sales velocity can be measured.")
else:
    actual = resolution[resolution["status"].astype(str).str.startswith("ok")].copy()
    actual["day"] = pd.to_datetime(actual["collected_at"], utc=True).dt.tz_convert(cfg["screenings"]["timezone"]).dt.date
    actual = actual.sort_values("collected_at").drop_duplicates(["url", "day"], keep="last")
    records = []
    for show_date, group in actual.groupby("show_date"):
        group = group.sort_values("day")
        group["velocity"] = group["tickets_sold"].diff() / pd.to_datetime(group["day"]).diff().dt.days
        group["acceleration"] = group["velocity"].diff()
        group["show"] = str(show_date)[:10]
        records.append(group)
    if records:
        observed = pd.concat(records)
        c1, c2 = st.columns(2)
        for holder, field, title in [(c1, "velocity", "Sales velocity: tickets per day"), (c2, "acceleration", "Change in velocity")]:
            fig = go.Figure()
            for name, group in observed.groupby("show"):
                fig.add_trace(go.Scatter(x=group["day"], y=group[field], mode="lines+markers", name=name))
            fig.update_layout(title=title, height=350)
            holder.plotly_chart(fig, width="stretch")
        st.caption("Daily differences are descriptive. Aggregate seat movement alone cannot identify the ad area or creative that caused a sale.")
