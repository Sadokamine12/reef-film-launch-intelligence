"""Audience and local advertising geography for Resolution @ ESO Supernova."""
from __future__ import annotations

import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from project_config import load_config
from ui import apply_theme, page_intro

st.set_page_config(page_title="Audiences | REEF", page_icon="🗺️", layout="wide")
apply_theme()
page_intro(
    "Audience geography",
    "Audiences & Geography",
    "Start close to ESO, prioritise the local/U6 catchment, and expand only when nearer audiences are efficient and a screening still needs demand.",
)

cfg = load_config()
venue = cfg["venue"]
lat0, lon0 = float(venue["lat"]), float(venue["lon"])

def circle(lat: float, lon: float, radius_km: float, n: int = 96):
    earth = 6371.0088
    lat1, lon1 = math.radians(lat), math.radians(lon)
    angular = radius_km / earth
    lats, lons = [], []
    for i in range(n + 1):
        bearing = 2 * math.pi * i / n
        lat2 = math.asin(math.sin(lat1)*math.cos(angular)+math.cos(lat1)*math.sin(angular)*math.cos(bearing))
        lon2 = lon1 + math.atan2(math.sin(bearing)*math.sin(angular)*math.cos(lat1), math.cos(angular)-math.sin(lat1)*math.sin(lat2))
        lats.append(math.degrees(lat2)); lons.append(math.degrees(lon2))
    return lats, lons

c1,c2,c3,c4 = st.columns(4)
c1.metric("Zone A · Core", "0–15 km", "50% paid-reach guide")
c2.metric("Zone B · Catchment", "15–30 km", "35% paid-reach guide")
c3.metric("Zone C · Expansion", "30–50 km", "15% test-only")
c4.metric("Starting audience", "20–60", "Broad local adults")

map_col, rules_col = st.columns([1.65,.85],gap="small")
with map_col:
    st.markdown("## Local catchment")
    fig = go.Figure()
    for radius, name, fill, line in [
        (50, "Zone C · Expansion", "rgba(181,107,21,.05)", "rgba(181,107,21,.38)"),
        (30, "Zone B · Munich catchment", "rgba(43,93,145,.07)", "rgba(43,93,145,.50)"),
        (15, "Zone A · Core", "rgba(8,126,131,.12)", "rgba(8,126,131,.72)"),
    ]:
        lats,lons=circle(lat0,lon0,radius)
        fig.add_trace(go.Scattermap(lat=lats,lon=lons,mode="lines",fill="toself",fillcolor=fill,line=dict(color=line,width=2),name=name,hoverinfo="name"))
    fig.add_trace(go.Scattermap(
        lat=[lat0],lon=[lon0],mode="markers+text",marker=dict(size=17,color="#102A43"),
        text=["ESO Supernova"],textposition="top center",name="ESO Supernova",
        hovertemplate="<b>ESO Supernova</b><br>Resolution screening venue<extra></extra>",
    ))
    fig.update_layout(
        map=dict(style="open-street-map",center=dict(lat=lat0,lon=lon0),zoom=7.9),
        height=510,margin=dict(l=0,r=0,t=0,b=0),showlegend=True,
        legend=dict(orientation="h",yanchor="bottom",y=1.01,xanchor="left",x=0,font=dict(size=9)),
    )
    st.plotly_chart(fig,width="stretch",config={"displaylogo":False,"scrollZoom":True})
with rules_col:
    st.markdown("## Activation rules")
    rules=pd.DataFrame([
        ["Zone A","Always first","ESO/Garching + immediate U6/research catchment"],
        ["Zone B","Primary scale","Munich/north-Munich catchment after Zone A has delivery"],
        ["Zone C","Test only","Activate only if a show is behind and nearer zones are efficient"],
    ],columns=["Zone","Role","Rule"])
    st.dataframe(rules,hide_index=True,width="stretch")
    st.success("Do not start Germany-wide. The first objective is to learn whether nearby audiences can fill the four Tuesday screenings efficiently.")
    st.info("Keep each screening date visible in the ad so spend and sales pace can be tied to the Tuesday that actually needs help.")

st.markdown("## Channel-specific audience setup")
m1,m2,m3 = st.columns(3,gap="small")
with m1:
    st.html('<div style="background:#fff;border:1px solid #DCE5EC;border-radius:9px;padding:12px"><b style="font-size:11px;color:#102A43">Meta</b><p style="font-size:9px;color:#526477;margin:5px 0 0">Adults 20–60 · broad local targeting · Zone A + B first · Creative A/B controlled.</p></div>')
with m2:
    st.html('<div style="background:#fff;border:1px solid #DCE5EC;border-radius:9px;padding:12px"><b style="font-size:11px;color:#102A43">Google Search</b><p style="font-size:9px;color:#526477;margin:5px 0 0">Garching/Munich catchment · high-intent event and planetarium searches · direct booking CTA.</p></div>')
with m3:
    st.html('<div style="background:#fff;border:1px solid #DCE5EC;border-radius:9px;padding:12px"><b style="font-size:11px;color:#102A43">Expansion</b><p style="font-size:9px;color:#526477;margin:5px 0 0">Use 30–50 km only after local delivery is understood and a specific screening remains below target.</p></div>')

st.markdown("## What changes after sales start")
st.dataframe(pd.DataFrame([
    ["ON TRACK","No geography expansion","€0 extra"],
    ["WATCH","Zone A + strongest nearby audience","Small 72-hour correction"],
    ["ACTION","Zone A + B; test C only if needed","€15–€25/day for 72h"],
    ["NEAR FULL","Stop ads for that date","Promote next available Tuesday"],
],columns=["Ticket state","Geography action","Budget action"]),hide_index=True,width="stretch")
