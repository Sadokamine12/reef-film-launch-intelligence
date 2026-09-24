from __future__ import annotations

import pandas as pd

META_ALIASES = {
    "date": "date",
    "campaign": "campaign_id",
    "campaign name": "campaign_id",
    "ad set id": "adset_id",
    "ad set name": "area",
    "ad name": "creative",
    "amount spent": "spend_eur",
    "amount spent (eur)": "spend_eur",
    "spend": "spend_eur",
    "impressions": "impressions",
    "reach": "reach",
    "clicks": "clicks",
    "link clicks": "clicks",
    "landing page views": "landing_page_views",
    "website purchases": "platform_purchases",
    "website purchases conversion value": "platform_purchase_value",
    "age": "age_band",
}
GOOGLE_ALIASES = {
    "day": "date",
    "date": "date",
    "campaign": "campaign_id",
    "campaign name": "campaign_id",
    "ad group": "area",
    "ad group name": "area",
    "ad group id": "adset_id",
    "ad": "creative",
    "ad name": "creative",
    "cost": "spend_eur",
    "cost (eur)": "spend_eur",
    "impressions": "impressions",
    "clicks": "clicks",
    "conversions": "platform_purchases",
    "conversion value": "platform_purchase_value",
}


def _norm(s: str) -> str:
    return str(s).strip().lower().replace("_", " ")


def normalize_platform_export(df: pd.DataFrame, provider: str, city: str, default_area: str = "All", default_age: str = "20-60") -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    provider_key = provider.strip().lower()
    aliases = META_ALIASES if provider_key in {"meta", "facebook", "meta ads"} else GOOGLE_ALIASES
    rename = {c: aliases.get(_norm(c), c) for c in df.columns}
    out = df.rename(columns=rename).copy()

    out["channel"] = "Meta" if provider_key in {"meta", "facebook", "meta ads"} else "Google Search"
    out["source_platform"] = "meta_ads" if out["channel"].iloc[0] == "Meta" else "google_ads"
    out["city"] = city

    if "area" not in out.columns:
        out["area"] = default_area
    out["area"] = out["area"].fillna("").astype(str).str.strip().replace("", default_area)
    if "age_band" not in out.columns:
        out["age_band"] = default_age
    out["age_band"] = out["age_band"].fillna("").astype(str).str.strip().replace("", default_age)
    if "creative" not in out.columns:
        out["creative"] = out.get("campaign_id", pd.Series("Unknown", index=out.index)).astype(str)
    out["creative"] = out["creative"].fillna("").astype(str).str.strip().replace("", "Unknown")

    for col in ["spend_eur", "impressions", "reach", "clicks", "landing_page_views", "platform_purchases", "platform_purchase_value"]:
        if col not in out.columns:
            out[col] = pd.NA
    if "date" not in out.columns:
        raise ValueError("Could not find a date column in the provider export.")
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if out["date"].isna().any():
        raise ValueError("Provider export contains invalid dates.")

    # Platform purchase metrics are diagnostics only. Never turn them into
    # attributed or incremental tickets without explicit verification.
    out["tickets_attributed"] = pd.NA
    out["incremental_tickets_estimate"] = pd.NA
    out["label_source"] = ""
    out["attribution_level"] = ""
    return out
