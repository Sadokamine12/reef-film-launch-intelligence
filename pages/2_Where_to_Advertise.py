"""Local advertising catchment for Resolution @ ESO Supernova."""
from __future__ import annotations

import math

import plotly.graph_objects as go
import streamlit as st

from launch_strategy import geography_plan
from project_config import load_config
from ui import apply_theme, page_intro

st.set_page_config(page_title="Where to Advertise | REEF", page_icon="🗺️", layout="wide")
apply_theme()
page_intro("Media geography", "Where to Advertise", "Start close to ESO. Expand only when the closer catchment has enough delivery and a screening still needs demand.")

cfg = load_config()
venue = cfg["venue"]
lat0, lon0 = float(venue["lat"]), float(venue["lon"])

def circle(lat: float, lon: float, radius_km: float, n: int = 96):
    earth = 6371.0088
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    angular = radius_km / earth
    lats, lons = [], []
    for i in range(n + 1):
        bearing = 2 * math.pi * i / n
        lat2 = math.asin(math.sin(lat1)*math.cos(angular)+math.cos(lat1)*math.sin(angular)*math.cos(bearing))
        lon2 = lon1 + math.atan2(math.sin(bearing)*math.sin(angular)*math.cos(lat1), math.cos(angular)-math.sin(lat1)*math.sin(lat2))
        lats.append(math.degrees(lat2)); lons.append(math.degrees(lon2))
    return lats, lons

c1,c2,c3 = st.columns(3)
c1.metric("Zone A", "0–15 km", "50% of local paid reach guide")
c2.metric("Zone B", "15–30 km", "35% of local paid reach guide")
c3.metric("Zone C", "30–50 km", "15% test-only expansion")

fig = go.Figure()
for radius, name, fill, line in [
    (50, "Zone C · Expansion", "rgba(181,107,21,.06)", "rgba(181,107,21,.45)"),
    (30, "Zone B · Munich catchment", "rgba(43,93,145,.08)", "rgba(43,93,145,.55)"),
    (15, "Zone A · Core", "rgba(8,126,131,.11)", "rgba(8,126,131,.70)"),
]:
    lats,lons=circle(lat0,lon0,radius)
    fig.add_trace(go.Scattermap(lat=lats,lon=lons,mode="lines",fill="toself",fillcolor=fill,line=dict(color=line,width=2),name=name,hoverinfo="name"))
fig.add_trace(go.Scattermap(
    lat=[lat0],lon=[lon0],mode="markers+text",marker=dict(size=18,color="#14283D"),
    text=["ESO Supernova"],textposition="top center",name="ESO Supernova",
    hovertemplate="<b>ESO Supernova</b><br>Resolution screening venue<extra></extra>",
))
fig.update_layout(
    map=dict(style="open-street-map",center=dict(lat=lat0,lon=lon0),zoom=7.8),
    height=650,margin=dict(l=0,r=0,t=0,b=0),showlegend=True,
    legend=dict(orientation="h",yanchor="bottom",y=1.01,xanchor="left",x=0),
)
st.plotly_chart(fig,width="stretch",config={"displaylogo":False,"scrollZoom":True})

st.markdown("## Operating geography")
st.dataframe(geography_plan(),hide_index=True,width="stretch")
st.info("The circles are **planning catchments**, not proof that every location inside them performs equally. Real campaign data should decide whether Zone B or C deserves more spend.")

st.markdown("## Practical setup")
st.markdown("""
**Meta / Instagram / Facebook**
- Start with **Zone A (0–15 km)** and **Zone B (15–30 km)**.
- Audience: adults 20–60, broad enough for the algorithm to learn.
- Use only the two approved creative angles.
- Keep the screening date in the ad so spend can be tied to the Tuesday that needs help.

**Google Search**
- Target Munich/Garching catchment and high-intent queries around planetarium, immersive experience and local February events.
- Send traffic directly to the most relevant available booking page.

**Zone C (30–50 km)**
- Do not activate by default.
- Use only when the nearer catchment has enough delivery, cost is acceptable and a screening is still below its booking curve.
""")

st.markdown("## What changes after sales start")
st.dataframe(
    __import__("pandas").DataFrame([
        ["Show on track","No expansion","€0 extra"],
        ["Show in WATCH","Zone A + strongest nearby catchment","Small 72-hour correction"],
        ["Show in ACTION","Zone A + B; test C only if needed","€15–€25/day for 72h"],
        ["Show near full","Stop ads for that date","Promote next available Tuesday"],
    ],columns=["Ticket state","Geography action","Budget action"]),
    hide_index=True,width="stretch",
)
