from __future__ import annotations

from pathlib import Path
import hashlib
import pandas as pd

from data_contracts import CAMPAIGN_COLUMNS, ensure_campaign_frame, read_csv_safe

CAMPAIGN_PATH = Path("data/campaign_history.csv")
REQUIRED_IMPORT = {"date", "channel", "area", "age_band", "creative", "spend_eur", "impressions", "clicks"}
VERIFIED_SOURCES = {"platform_conversion", "promo_code", "eso_source_report", "controlled_residual", "staggered_test"}


def validate_campaign_rows(df: pd.DataFrame) -> list[str]:
    """Reject ambiguous exports and impossible metrics before any disk write."""
    errors = []
    missing = sorted(REQUIRED_IMPORT - set(df.columns))
    if missing:
        return ["Missing required mapped columns: " + ", ".join(missing)]
    for field in ("date", "channel", "area", "age_band", "creative"):
        if df[field].fillna("").astype(str).str.strip().eq("").any():
            errors.append(f"{field} has blank values")
    if pd.to_datetime(df["date"], errors="coerce").isna().any():
        errors.append("date contains invalid values")
    for field in ("spend_eur", "impressions", "reach", "clicks", "video_views_75", "landing_page_views", "platform_purchases", "platform_purchase_value", "tickets_attributed", "incremental_tickets_estimate"):
        if field not in df:
            continue
        values = pd.to_numeric(df[field].replace("", pd.NA), errors="coerce")
        supplied = df[field].notna() & df[field].astype(str).str.strip().ne("")
        if (supplied & (values.isna() | values.lt(0))).any():
            errors.append(f"{field} contains invalid or negative values")
    imp = pd.to_numeric(df["impressions"], errors="coerce")
    clicks = pd.to_numeric(df["clicks"], errors="coerce")
    if clicks.gt(imp).any():
        errors.append("clicks exceed impressions")
    if "tickets_attributed" in df or "incremental_tickets_estimate" in df:
        ticket = pd.to_numeric(df.get("tickets_attributed", pd.Series(index=df.index, dtype=float)), errors="coerce").notna()
        lift = pd.to_numeric(df.get("incremental_tickets_estimate", pd.Series(index=df.index, dtype=float)), errors="coerce").notna()
        source = df.get("label_source", pd.Series("", index=df.index)).fillna("").astype(str).str.lower()
        if ((ticket | lift) & ~source.isin(VERIFIED_SOURCES)).any():
            errors.append("ticket labels require a verified label_source")
    return errors


def ensure_campaign_file(path: str | Path = CAMPAIGN_PATH) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists() or p.stat().st_size == 0:
        pd.DataFrame(columns=CAMPAIGN_COLUMNS).to_csv(p, index=False)
    return p


def _read(path: str | Path = CAMPAIGN_PATH) -> pd.DataFrame:
    return ensure_campaign_frame(read_csv_safe(path))


def make_observation_id(row: dict) -> str:
    basis = "|".join(str(row.get(k, "")).strip() for k in [
        "date", "show_date", "channel", "city", "area", "age_band", "creative", "campaign_id", "adset_id", "test_id"
    ])
    return hashlib.sha1(basis.encode("utf-8", errors="ignore")).hexdigest()[:16]


def append_observations(new_rows: pd.DataFrame, path: str | Path = CAMPAIGN_PATH) -> tuple[int, int]:
    if new_rows is None or new_rows.empty:
        return 0, len(_read(path))
    old = _read(path)
    new = ensure_campaign_frame(new_rows)
    errors = validate_campaign_rows(new)
    if errors:
        raise ValueError("; ".join(errors))
    ids = []
    for _, r in new.iterrows():
        explicit = str(r.get("observation_id", "")).strip()
        ids.append(explicit or make_observation_id(r.to_dict()))
    new["observation_id"] = ids
    before_ids = set(old["observation_id"].astype(str))
    combined = pd.concat([old, new], ignore_index=True)
    combined = combined.drop_duplicates(subset=["observation_id"], keep="last")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False)
    net_new = len(set(combined["observation_id"].astype(str)) - before_ids)
    return net_new, len(combined)


def import_campaign_csv(uploaded_df: pd.DataFrame, path: str | Path = CAMPAIGN_PATH) -> tuple[int, int, list[str]]:
    if uploaded_df is None or uploaded_df.empty:
        return 0, len(_read(path)), ["Uploaded file is empty."]
    df = uploaded_df.copy()
    aliases = {
        "spend": "spend_eur", "amount_spent": "spend_eur", "amount spent": "spend_eur",
        "amount spent (eur)": "spend_eur", "cost": "spend_eur", "day": "date", "reporting starts": "date",
        "impressions": "impressions", "link clicks": "clicks", "clicks (all)": "clicks",
        "views_75": "video_views_75", "video_75": "video_views_75", "video plays at 75%": "video_views_75",
        "landing_views": "landing_page_views", "lpv": "landing_page_views", "landing page views": "landing_page_views",
        "reach": "reach", "purchases": "platform_purchases", "website purchases": "platform_purchases",
        "purchase conversion value": "platform_purchase_value", "website purchases conversion value": "platform_purchase_value",
        "tickets": "tickets_attributed", "city": "city", "market": "city", "geo": "area", "audience": "age_band", "ad set id": "adset_id",
        "campaign id": "campaign_id", "ad name": "creative", "ad set name": "area", "source platform": "source_platform",
    }
    rename = {}
    for c in df.columns:
        key = str(c).strip().lower()
        rename[c] = aliases.get(key, c)
    df = df.rename(columns=rename)
    warnings = validate_campaign_rows(df)
    if warnings:
        return 0, len(_read(path)), warnings
    added, total = append_observations(df, path)
    return added, total, warnings


def campaign_summary(path: str | Path = CAMPAIGN_PATH) -> dict:
    df = _read(path)
    numeric = ["spend_eur", "impressions", "reach", "video_views_75", "clicks", "landing_page_views", "platform_purchases", "platform_purchase_value", "tickets_attributed", "incremental_tickets_estimate"]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    verified_sources = VERIFIED_SOURCES
    source = df["label_source"].fillna("").astype(str).str.lower()
    ticket_label = df[["tickets_attributed", "incremental_tickets_estimate"]].notna().any(axis=1)
    return {
        "rows": len(df),
        "spend_eur": float(df["spend_eur"].sum(skipna=True) or 0),
        "cities": int(df["city"].replace("", pd.NA).dropna().nunique()),
        "areas": int(df["area"].replace("", pd.NA).dropna().nunique()),
        "ages": int(df["age_band"].replace("", pd.NA).dropna().nunique()),
        "creatives": int(df["creative"].replace("", pd.NA).dropna().nunique()),
        "channels": int(df["channel"].replace("", pd.NA).dropna().nunique()),
        "engagement_rows": int(df[["impressions", "clicks", "video_views_75", "landing_page_views"]].notna().any(axis=1).sum()),
        "ticket_rows": int(ticket_label.sum()),
        "verified_ticket_rows": int((ticket_label & source.isin(verified_sources)).sum()),
    }


def attribution_readiness(path: str | Path = CAMPAIGN_PATH) -> dict:
    df = _read(path)
    summary = campaign_summary(path)
    has_campaign_ids = bool(df["campaign_id"].replace("", pd.NA).notna().any())
    has_adset_ids = bool(df["adset_id"].replace("", pd.NA).notna().any())
    has_utm = bool(df["utm_campaign"].replace("", pd.NA).notna().any())
    has_label_source = bool(df["label_source"].replace("", pd.NA).notna().any())
    score = sum([has_campaign_ids, has_adset_ids, has_utm, has_label_source, summary["verified_ticket_rows"] > 0]) * 20
    sources = set(df["label_source"].fillna("").astype(str).str.lower())
    if "eso_source_report" in sources:
        level = "A"
    elif "promo_code" in sources:
        level = "B"
    elif "platform_conversion" in sources:
        level = "C"
    elif sources & {"controlled_residual", "staggered_test"}:
        level = "D"
    else:
        level = "E"
    if summary["verified_ticket_rows"] > 0:
        label = "Ticket attribution active"
    elif has_utm and has_campaign_ids:
        label = "Engagement attribution ready; purchase attribution still missing"
    else:
        label = "Attribution setup incomplete"
    return {
        "score": int(score), "level": level, "label": label, "campaign_ids": has_campaign_ids, "adset_ids": has_adset_ids,
        "utm": has_utm, "label_source": has_label_source, **summary,
    }
