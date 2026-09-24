from __future__ import annotations

from pathlib import Path
import re
import pandas as pd
import numpy as np

ESO_SNAPSHOT_COLUMNS = [
    "collected_at_utc", "programme_title", "show_datetime_local", "weekday", "start_hour", "month",
    "minimum_age", "ticket_price_eur", "duration_min", "available_seats", "capacity",
    "tickets_sold_so_far", "days_to_event", "programme_url", "source_type", "retrieval_mode", "status",
]

CAMPAIGN_COLUMNS = [
    "observation_id", "date", "show_date", "days_to_event", "experiment_wave", "control_group",
    "channel", "city", "area", "age_band", "creative", "spend_eur", "impressions", "video_views_75",
    "clicks", "landing_page_views", "tickets_attributed", "incremental_tickets_estimate",
    "label_source", "attribution_level", "campaign_id", "adset_id", "test_id", "utm_campaign",
    "utm_content", "notes",
]


def canonical_booking_id(url: str) -> str:
    s = str(url or "")
    m = re.search(r"/booking/([^/?#]+)/?", s, flags=re.I)
    return m.group(1).strip().lower() if m else ""


def clean_eso_snapshots(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=ESO_SNAPSHOT_COLUMNS)
    out = df.copy()
    for c in ESO_SNAPSHOT_COLUMNS:
        if c not in out.columns:
            out[c] = pd.NA
    if "source_type" in out.columns:
        out = out[out["source_type"].astype(str).eq("booking_page")]
    if "status" in out.columns:
        out = out[out["status"].astype(str).str.startswith("ok")]
    for c in ["available_seats", "capacity", "tickets_sold_so_far", "days_to_event", "start_hour", "month", "minimum_age", "ticket_price_eur", "duration_min"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["programme_title", "show_datetime_local", "available_seats", "capacity", "days_to_event"])
    out["show_datetime_parsed"] = pd.to_datetime(out["show_datetime_local"], errors="coerce")
    out = out.dropna(subset=["show_datetime_parsed"])
    out = out[(out["capacity"] > 0) & (out["available_seats"] >= 0) & (out["available_seats"] <= out["capacity"])]
    out = out[~out["programme_title"].astype(str).str.contains("cookie|weitere information|more information|kategorien der von uns|unknown programme", case=False, regex=True, na=False)]
    actual_sold = out["capacity"] - out["available_seats"]
    out = out[out["tickets_sold_so_far"].isna() | out["tickets_sold_so_far"].eq(actual_sold)]
    out["tickets_sold_so_far"] = out["capacity"] - out["available_seats"]
    out["sold_fraction"] = (out["tickets_sold_so_far"] / out["capacity"]).clip(0, 1)
    out["booking_id"] = out["programme_url"].map(canonical_booking_id)
    out = out[out["booking_id"].ne("")]
    fallback = out["programme_title"].astype(str).str.strip() + " | " + out["show_datetime_local"].astype(str).str.strip()
    out["show_key"] = np.where(out["booking_id"].astype(str).str.len() > 0, out["booking_id"], fallback)
    out["collected_at_dt"] = pd.to_datetime(out["collected_at_utc"], errors="coerce", utc=True)
    out["snapshot_day"] = out["collected_at_dt"].dt.tz_convert("Europe/Berlin").dt.strftime("%Y-%m-%d")
    out = out.dropna(subset=["collected_at_dt"])
    # One canonical booking observation per calendar day. This collapses EN/DE URLs for the same booking id.
    out = out.sort_values(["show_key", "snapshot_day", "collected_at_dt"]).drop_duplicates(["show_key", "snapshot_day"], keep="last")
    out = out[out["days_to_event"].between(0, 180)]
    return out.reset_index(drop=True)


def ensure_campaign_frame(df: pd.DataFrame | None = None) -> pd.DataFrame:
    out = pd.DataFrame() if df is None else df.copy()
    for c in CAMPAIGN_COLUMNS:
        if c not in out.columns:
            out[c] = ""
    return out[CAMPAIGN_COLUMNS]


def read_csv_safe(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()
