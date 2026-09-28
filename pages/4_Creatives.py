"""Creative execution briefs for the Resolution launch."""
from __future__ import annotations

import streamlit as st

from project_config import load_config
from ui import apply_theme, page_intro

POSTER = "https://reef-distribution.com/wp-content/uploads/2026/03/POSTER_withCredits_40X27CinephonicTagline-768x1138.jpg"
ESO_NIGHT = "https://supernova.eso.org/static/archives/images/screen/2018_04_14_Supernova_Night-CC.jpg"

st.set_page_config(page_title="Creatives | REEF", page_icon="🎨", layout="wide")
apply_theme()
page_intro(
    "Campaign assets",
    "Creative Plan",
    "Two controlled creative directions for launch. Keep the destination, dates and call-to-action consistent so results remain interpretable.",
)

cfg = load_config()

st.html(
    """
    <style>
    .creative-hero{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:8px}
    .creative-card{background:#fff;border:1px solid #DCE5EC;border-radius:10px;overflow:hidden}
    .creative-image{height:210px;background-size:cover;background-position:center;position:relative}
    .creative-image:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(5,18,32,.04),rgba(5,18,32,.68))}
    .creative-badge{position:absolute;z-index:2;left:14px;top:14px;background:#0C526E;color:white;font-size:9px;font-weight:800;padding:4px 8px;border-radius:999px}
    .creative-copy{padding:14px 16px}
    .creative-copy h3{font-size:14px!important;margin:0 0 5px!important}
    .creative-copy p{font-size:10px;margin:0;color:#526477;line-height:1.4}
    .creative-specs{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:10px}
    .creative-specs div{background:#F5F8FA;border:1px solid #E3EAF0;border-radius:7px;padding:8px}
    .creative-specs span{display:block;font-size:7px;color:#6B7D8C;text-transform:uppercase;letter-spacing:.06em}
    .creative-specs b{display:block;font-size:9px;color:#193B55;margin-top:2px}
    .copy-box{background:white;border:1px solid #DCE5EC;border-radius:9px;padding:12px 14px;margin-top:10px}
    .copy-box b{font-size:10px;color:#173A54}
    .copy-box p{font-size:10px;color:#38566D;margin:5px 0 0}
    @media(max-width:900px){.creative-hero{grid-template-columns:1fr}}
    </style>
    """
)

left, right = st.columns(2, gap="small")
with left:
    st.html(
        f"""
        <div class="creative-card">
          <div class="creative-image" style="background-image:url('{POSTER}')">
            <div class="creative-badge">CREATIVE A · EXPERIENCE</div>
          </div>
          <div class="creative-copy">
            <h3>Sell the immersive experience</h3>
            <p>Lead with music, light, motion and the feeling of entering another world. This is the broad discovery creative for social feeds.</p>
            <div class="creative-specs">
              <div><span>Primary</span><b>Meta Reels / Stories</b></div>
              <div><span>Audience</span><b>20–60 broad local</b></div>
              <div><span>CTA</span><b>Experience Resolution</b></div>
            </div>
          </div>
        </div>
        """
    )
with right:
    st.html(
        f"""
        <div class="creative-card">
          <div class="creative-image" style="background-image:url('{ESO_NIGHT}')">
            <div class="creative-badge">CREATIVE B · EVENT</div>
          </div>
          <div class="creative-copy">
            <h3>Sell the date and venue</h3>
            <p>Lead with ESO Supernova, the exact Tuesday, Garching/U6 access and a clear ticket action. This is the high-intent local event creative.</p>
            <div class="creative-specs">
              <div><span>Primary</span><b>Meta + Search</b></div>
              <div><span>Audience</span><b>Local event intent</b></div>
              <div><span>CTA</span><b>Book this Tuesday</b></div>
            </div>
          </div>
        </div>
        """
    )

st.markdown("## Approved message framework")
m1, m2, m3 = st.columns(3, gap="small")
with m1:
    st.html('<div class="copy-box"><b>Opening hook</b><p>Music. Light. A 46-minute immersive journey inside the dome.</p></div>')
with m2:
    st.html('<div class="copy-box"><b>Event proof</b><p>Resolution at ESO Supernova · Garching · Tuesday screening.</p></div>')
with m3:
    st.html('<div class="copy-box"><b>Access line</b><p>Four minutes on foot from U6 Garching Forschungszentrum.</p></div>')

st.markdown("## Production checklist")
check = st.columns(4, gap="small")
for col, title, detail in zip(
    check,
    ["Vertical cut", "Square cut", "Event card", "Tracking"],
    ["9:16 · 10–20 sec", "1:1 · feed-safe", "Exact date + venue", "One UTM per creative"],
):
    with col:
        st.metric(title, detail)

st.info(
    "Keep Creative A and B comparable in duration, destination URL and campaign objective. Change the message angle, not everything at once."
)
