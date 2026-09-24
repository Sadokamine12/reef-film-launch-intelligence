"""Import and inspect genuine campaign observations."""
from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st

from campaign_lab import CAMPAIGN_PATH, REQUIRED_IMPORT, append_observations, attribution_readiness, campaign_summary, import_campaign_csv
from data_contracts import ensure_campaign_frame, read_csv_safe
from training_engine import run_all_training
from platform_import import normalize_platform_export
from ui import apply_theme, editing_enabled, page_intro, select_market

st.set_page_config(page_title="Campaign Data | REEF", page_icon="📥", layout="wide")
apply_theme()
page_intro("Measured marketing", "Campaign Data", "Import actual Meta or Google results, verify each field, and keep ticket-label provenance visible.")
with st.sidebar:
    st.markdown("### Test market")
    market = select_market()
summary, attr = campaign_summary(), attribution_readiness()
cols = st.columns(4)
for col, label, value in zip(cols,
    ["Campaign rows", "Actual spend", "Engagement rows", "Attribution level"],
    [str(summary["rows"]), f"EUR {summary['spend_eur']:.0f}", str(summary["engagement_rows"]), attr["level"]]):
    col.metric(label, value)

if summary["rows"] == 0:
    st.info("No campaign results have been imported. The dashboard shows planning assumptions until real ad results arrive. Start with the EUR 90 first wave after the no-paid booking window.")
else:
    st.caption(f"{summary['verified_ticket_rows']} tracked-ticket rows. Tracked purchases alone do not prove additional ticket lift.")

if not editing_enabled():
    st.info("This shared dashboard is view-only. Campaign imports and retraining run in the local project; publish the updated data and model files to refresh this link.")
    history = ensure_campaign_frame(read_csv_safe(CAMPAIGN_PATH))
    if history.empty:
        st.caption("No campaign observations have been published yet.")
    else:
        with st.expander("Published campaign observations"):
            st.dataframe(history, hide_index=True, width="stretch")
    st.stop()

st.markdown("## Fast import: Meta / Google export")
st.caption("For standard provider exports, auto-normalize the common fields first. Platform purchase metrics stay diagnostic and are never treated as ticket lift automatically.")
fast = st.file_uploader("Provider export CSV", type=["csv"], key="provider_export")
provider = st.selectbox("Provider", ["Meta Ads", "Google Ads"], key="provider_type")
if fast is not None:
    try:
        raw = pd.read_csv(fast)
        default_area = market.get("search_area", market["label"])
        normalized = normalize_platform_export(raw, provider, market["label"], default_area=default_area)
        with st.expander("Normalized preview", expanded=True):
            st.dataframe(normalized.head(20), hide_index=True, width="stretch")
        if st.button("Validate and import normalized export", type="primary", key="fast_import"):
            added, total, errors = import_campaign_csv(normalized)
            if errors:
                for message in errors:
                    st.error(message)
            else:
                st.success(f"Imported {added} observations; campaign history now has {total} rows.")
                st.rerun()
    except Exception as exc:
        st.error(f"Could not normalize this provider export: {exc}")

st.markdown("## Import a platform CSV")
st.caption("Upload a real daily export. Confirm the eight fields below; important fields are never silently guessed.")
upload = st.file_uploader("Meta or Google CSV", type=["csv"])
if upload is not None:
    try:
        source = pd.read_csv(upload)
        with st.expander("Preview uploaded rows", expanded=False):
            st.dataframe(source.head(10), hide_index=True, width="stretch")
        choices = ["— select —", *source.columns.tolist()]
        mapped = {}
        left, right = st.columns(2)
        for index, field in enumerate(sorted(REQUIRED_IMPORT)):
            match = next((c for c in source.columns if str(c).strip().lower().replace(" ", "_") == field), None)
            if field == "spend_eur" and match is None:
                match = next((c for c in source.columns if str(c).strip().lower() in {"amount spent", "amount spent (eur)", "cost"}), None)
            if field == "clicks" and match is None:
                match = next((c for c in source.columns if str(c).strip().lower() in {"link clicks", "clicks (all)"}), None)
            with (left if index % 2 == 0 else right):
                picked = st.selectbox(field.replace("_", " ").title(), choices, index=choices.index(match) if match in choices else 0, key=f"map_{field}")
            if picked != "— select —":
                mapped[field] = picked
        if st.button("Validate and import", type="primary"):
            if set(mapped) != REQUIRED_IMPORT or len(set(mapped.values())) != len(mapped):
                st.error("Map every required field to a different CSV column.")
            else:
                prepared = source.rename(columns={original: field for field, original in mapped.items()})
                if "city" not in prepared.columns or prepared["city"].fillna("").astype(str).str.strip().eq("").all():
                    prepared["city"] = market["label"]
                added, total, errors = import_campaign_csv(prepared)
                if errors:
                    for message in errors:
                        st.error(message)
                else:
                    st.success(f"Imported {added} observations; campaign history now has {total} rows.")
                    st.rerun()
    except Exception as exc:
        st.error(f"Could not read this CSV: {exc}")

with st.expander("Add one observation manually"):
    with st.form("campaign_obs"):
        a = st.columns(4)
        obs_date = a[0].date_input("Observation date", value=date.today())
        show_date = a[1].date_input("Screening date", value=date(2027, 2, 2))
        wave = a[2].selectbox("Phase", ["Baseline", "Geo + creative", "Age refinement", "Intent", "Scale"])
        channel = a[3].selectbox("Channel", ["Meta", "Google Search", "Retargeting", "Organic/Partner", "No paid media"])
        b = st.columns(4)
        city = market["label"]
        area_options = [z["area"] for z in market.get("zones", [])] + [market.get("search_area", city), "Prior site/video visitors", "All"]
        area = b[0].selectbox("Area", list(dict.fromkeys(area_options)))
        age = b[1].selectbox("Adults", ["20-60", "20-34", "35-60"])
        creative = b[2].selectbox("Creative", ["SXSW proof", "Music + 360 experience", "High-intent text", "Scarcity / next Tuesday", "None"])
        test_id = b[3].text_input("Test ID", placeholder="W1-01")
        st.caption(f"Selected market city: {city}")
        c = st.columns(5)
        spend = c[0].number_input("Spend (EUR)", min_value=0.0, step=1.0)
        impressions = c[1].number_input("Impressions", min_value=0, step=1)
        clicks = c[2].number_input("Clicks", min_value=0, step=1)
        views75 = c[3].number_input("75% video views", min_value=0, step=1)
        lpv = c[4].number_input("Landing-page views", min_value=0, step=1)
        campaign_id = st.text_input("Campaign ID")
        adset_id = st.text_input("Ad-set ID")
        verified = st.checkbox("I have a documented ticket or controlled-lift label")
        d = st.columns(4)
        tickets = d[0].number_input("Tracked tickets", min_value=0.0, step=1.0, disabled=not verified)
        lift = d[1].number_input("Controlled incremental estimate", min_value=0.0, step=1.0, disabled=not verified)
        source = d[2].selectbox("Label source", ["", "eso_source_report", "promo_code", "platform_conversion", "controlled_residual", "staggered_test"], disabled=not verified)
        attr_level = d[3].selectbox("Attribution level", ["", "A", "B", "C", "D", "E"], disabled=not verified)
        saved = st.form_submit_button("Save observation", type="primary")
    if saved:
        try:
            row = pd.DataFrame([{
                "date": obs_date.isoformat(), "show_date": show_date.isoformat(), "days_to_event": (show_date-obs_date).days,
                "experiment_wave": wave, "channel": channel, "city": city, "area": area, "age_band": age, "creative": creative,
                "test_id": test_id, "spend_eur": spend, "impressions": impressions, "clicks": clicks,
                "video_views_75": views75, "landing_page_views": lpv,
                "campaign_id": campaign_id, "adset_id": adset_id,
                "tickets_attributed": tickets if verified else "", "incremental_tickets_estimate": lift if verified else "",
                "label_source": source if verified else "", "attribution_level": attr_level if verified else "",
            }])
            added, total = append_observations(row)
            st.success(f"Saved {added} new row; {total} total.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

with st.expander("Review saved observations and train models"):
    if st.button("Train eligible models"):
        for result in run_all_training():
            st.write(f"{result.name}: {result.status.replace('_', ' ')} · {result.rows} rows · operational: {result.operational}")
    history = ensure_campaign_frame(read_csv_safe(CAMPAIGN_PATH))
    if history.empty:
        st.caption("No saved observations yet.")
    else:
        st.dataframe(history, hide_index=True, width="stretch")
        st.download_button("Download campaign history", history.to_csv(index=False).encode("utf-8"), "campaign_history.csv", "text/csv")
