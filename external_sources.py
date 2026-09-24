"""Read-only status helpers for external live data sources."""
from __future__ import annotations

from pathlib import Path
import json

STATUS_PATH = Path("data/external_source_status.json")


def load_external_source_status(path: str | Path = STATUS_PATH) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def source_readiness_rows(status: dict | None = None) -> list[dict]:
    status = status or load_external_source_status()
    rows = []
    meta = status.get("meta_ads", {})
    google = status.get("google_ads", {})
    eso = status.get("eso_resolution", {})
    rows.append({
        "Source": "Meta Ads",
        "Status": meta.get("status", "unknown"),
        "Ready": bool(meta.get("confirmed_reef_account")) and int(meta.get("usable_rows_last_2_years", 0) or 0) > 0,
        "Detail": meta.get("note", ""),
    })
    rows.append({
        "Source": "Google Ads",
        "Status": google.get("status", "unknown"),
        "Ready": bool(google.get("connected_account_present")),
        "Detail": google.get("note", ""),
    })
    found = int(eso.get("public_booking_urls_found", 0) or 0)
    expected = int(eso.get("expected_booking_urls", 4) or 4)
    rows.append({
        "Source": "ESO Resolution bookings",
        "Status": eso.get("status", "unknown"),
        "Ready": found >= expected and expected > 0,
        "Detail": f"{found}/{expected} URLs found. {eso.get('note', '')}".strip(),
    })
    return rows
