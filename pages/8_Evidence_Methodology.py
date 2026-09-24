"""Plain language provenance and limits for executive readers."""
from __future__ import annotations

import streamlit as st
from model_quality import eso_coverage, current_eso_model
from campaign_lab import campaign_summary
from ui import apply_theme, page_intro

st.set_page_config(page_title="Evidence & Methodology", page_icon="📚", layout="wide")
apply_theme()
page_intro("Source and interpretation", "Evidence & Methodology", "What is observed, fitted, and still hypothetical.")
c = eso_coverage()
m = current_eso_model()
h = campaign_summary()
st.markdown(f"""
### What is observed

ESO booking inventory: **{c['rows']} daily observations from {c['unique_shows']} booking IDs**, with {c['repeated_shows']} shows observed on more than one day. Each row is a booking page with a real seat count. Resolution has no configured public booking IDs yet.

### What is fitted

The monotone ESO curve is a descriptive fit to comparable shows. It estimates bookings at a given lead time, but the current sample does not observe the final days of sales. The learned demand model has grouped-by-booking MAE **{m.get('mae', 'n/a')} percentage points** and is operational only if it clears the quality gate and beats the empirical benchmark.

### What is a planning scenario

Paid lift, spend response, and occupancy probabilities before the campaign are hypotheses. Geographic test priority is based on travel and audience access, not an observed conversion probability. No age band, creative, channel, or Tuesday is a proven ticket winner.

### What would establish ticket lift

Direct ESO source reporting (A), unique codes (B), reliable sale events (C), or controlled holdout/staggered tests (D) can support stronger attribution. Aggregate seat movement alone (E) supports only an uncertain overall campaign comparison. Current campaign rows: **{h['rows']}**; controlled incremental labels: **0**.

### Decisions

Run the no-paid baseline first. Compare engagement during small, balanced tests. Move reserve only after measured performance supports it. Do not equate attributed purchases with additional purchases.
""")
