from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

CONFIG_PATH = Path("config/project.json")

DEFAULT_CONFIG = {
    "project_name": "Resolution @ ESO Supernova — Marketing Intelligence",
    "film": {
        "title": "Resolution: A Cinephonic Rhapsody for the Soul",
        "url": "https://reef-distribution.com/resolution/",
        "runtime_minutes": 46,
        "format": "Fulldome",
        "genre": "Immersive music / visual experience",
        "language": "English / music-led",
        "target_age_min": 20,
        "target_age_max": 60,
    },
    "venue": {
        "name": "ESO Supernova Planetarium & Visitor Centre",
        "address": "Karl-Schwarzschild-Str. 2, 85748 Garching bei München",
        "lat": 48.259828,
        "lon": 11.670136,
        "capacity_per_show": 109,
    },
    "screenings": {
        "dates": ["2027-02-02", "2027-02-09", "2027-02-16", "2027-02-23"],
        "time": "19:00",
        "timezone": "Europe/Berlin",
    },
    "screening_forecast": {
        "method": "calendar_campaign_prior_v1",
        "status": "scenario prior; not measured Tuesday performance",
        "note": "Used only to distribute the four-show planning forecast before Resolution-specific sales exist. Weights are transparent modelling assumptions informed by published calendar context and campaign maturity.",
        "sources": {
            "bavaria_school_holidays": "https://www.km.bayern.de/termine/ferien-und-feiertage",
            "tum_semester_dates": "https://www.tum.de/studium/bewerbung/infoportal-bewerbung/termine-und-fristen",
            "lmu_lecture_dates": "https://www.lmu.de/de/workspace-fuer-studierende/1x1-des-studiums/vorlesungszeiten/",
        },
        "shows": {
            "2027-02-02": {
                "weight": 0.96,
                "calendar_fact": "TUM and LMU winter lecture periods are still running through 5 February 2027.",
                "scenario_driver": "Opening screening: local campus presence helps, but campaign awareness and word-of-mouth have had the least time to mature.",
            },
            "2027-02-09": {
                "weight": 0.92,
                "calendar_fact": "Bavaria spring school holidays run 8–12 February 2027; TUM and LMU are already lecture-free.",
                "scenario_driver": "Holiday and lower campus presence are treated as a downside risk for this adult local-access campaign.",
            },
            "2027-02-16": {
                "weight": 1.08,
                "calendar_fact": "The Bavarian spring school holiday has ended; TUM and LMU remain lecture-free.",
                "scenario_driver": "Post-holiday week with a more mature campaign and retargeting pool is treated as the strongest planning week.",
            },
            "2027-02-23": {
                "weight": 1.04,
                "calendar_fact": "TUM and LMU remain lecture-free.",
                "scenario_driver": "Final screening combines mature remarketing and last-chance urgency, partly offset by late-run fatigue.",
            },
        },
    },
    "marketing": {
        "total_budget_eur": 500,
        "experiment_budget_eur": 240,
        "scale_reserve_eur": 260,
        "success_occupancy_pct": 60,
        "target_incremental_tickets": 40,
        "max_incremental_cpa_eur": 10,
    },
    "planning_prior": {
        "cpc_eur": 0.85,
        "incremental_tickets_per_click": 0.045,
        "status": "unverified scenario assumption",
    },
    "tracking": {
        "resolution_booking_urls": [],
        "utm_source_pattern": "meta|google",
        "utm_campaign_pattern": "resolution_eso_2027_02",
        "baseline_max_detail_pages": 30,
        "baseline_max_booking_pages": 24,
        "daily_collection": True,
    },
    "market_testing": {
        "default_city": "Garching / Munich North",
        "allow_custom_city": True,
        "note": "Target-market selection changes paid-media test geography only. ESO venue and empirical demand baseline remain fixed in Garching.",
    },
    "model_gates": {
        "engagement_min_rows": 12,
        "ticket_lift_min_rows": 18,
        "ticket_lift_min_areas": 3,
        "ticket_lift_min_creatives": 2,
        "operational_baseline_max_mae_pp": 12,
        "operational_baseline_min_r2": 0.0,
        "operational_marketing_max_mae_tickets": 5,
    },
}


def _deep_merge(base: dict, update: dict) -> dict:
    out = deepcopy(base)
    for key, value in (update or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | Path = CONFIG_PATH) -> dict:
    p = Path(path)
    if not p.exists():
        return deepcopy(DEFAULT_CONFIG)
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(DEFAULT_CONFIG)
    return _deep_merge(DEFAULT_CONFIG, payload)


def save_config(cfg: dict, path: str | Path = CONFIG_PATH) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def total_capacity(cfg: dict | None = None) -> int:
    cfg = cfg or load_config()
    cap = int(cfg["venue"].get("capacity_per_show", 109))
    return cap * len(cfg["screenings"].get("dates", []))


def flat_context(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    return {
        "film_title": cfg["film"]["title"],
        "venue": cfg["venue"]["name"],
        "capacity_per_show": int(cfg["venue"]["capacity_per_show"]),
        "show_dates": list(cfg["screenings"]["dates"]),
        "screening_forecast": deepcopy(cfg.get("screening_forecast", {})),
        "budget_eur": float(cfg["marketing"]["total_budget_eur"]),
        "target_age_min": int(cfg["film"]["target_age_min"]),
        "target_age_max": int(cfg["film"]["target_age_max"]),
    }
