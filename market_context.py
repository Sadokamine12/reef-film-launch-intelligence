"""Target-market presets for the paid-media experiment.

These are planning centres for ad testing, not claims about measured demand.
The screening venue and ESO empirical demand baseline remain fixed in Garching.
"""
from __future__ import annotations

from copy import deepcopy

from project_config import load_config


DEFAULT_MARKETS = {
    "Garching / Munich North": {
        "label": "Garching / Munich North",
        "search_area": "Garching + Munich North",
        "center": {"lat": 48.247, "lon": 11.640},
        "show_u6": True,
        "zones": [
            {
                "area": "ESO / Forschungszentrum",
                "lat": 48.259828, "lon": 11.670136, "radius_km": 2.5,
                "role": "Venue / campus", "age": "20–60",
                "why": "Venue, research campus and immediate catchment",
                "creative": "SXSW proof + immersive dome experience",
            },
            {
                "area": "Garching / Hochbrück",
                "lat": 48.247326, "lon": 11.631008, "radius_km": 2.5,
                "role": "Local", "age": "20–60",
                "why": "Local residents, workers and direct U6 access",
                "creative": "Four Tuesday nights + easy local access",
            },
            {
                "area": "Universität / Schwabing",
                "lat": 48.150850, "lon": 11.580250, "radius_km": 2.5,
                "role": "Culture / university", "age": "20–60",
                "why": "University, culture and music audience on the U6 corridor",
                "creative": "Award-winning immersive music event",
            },
        ],
    },
    "Munich": {
        "label": "Munich",
        "search_area": "Munich",
        "center": {"lat": 48.154, "lon": 11.581},
        "show_u6": True,
        "zones": [
            {
                "area": "Universität / Schwabing",
                "lat": 48.150850, "lon": 11.580250, "radius_km": 2.5,
                "role": "Culture / university", "age": "20–60",
                "why": "University, culture and music audience with direct U6 access",
                "creative": "Award-winning immersive music event",
            },
            {
                "area": "Maxvorstadt",
                "lat": 48.148500, "lon": 11.565500, "radius_km": 2.5,
                "role": "Culture", "age": "20–60",
                "why": "Dense cultural, student and young-professional catchment",
                "creative": "Music + 360° visual experience",
            },
            {
                "area": "Studentenstadt / Freimann",
                "lat": 48.183522, "lon": 11.607710, "radius_km": 2.5,
                "role": "U6 corridor", "age": "20–60",
                "why": "Direct U6 path toward the venue and younger adult audience",
                "creative": "Immersive experience + direct U6 access",
            },
        ],
    },
    "Freising": {
        "label": "Freising",
        "search_area": "Freising",
        "center": {"lat": 48.4029, "lon": 11.7485},
        "show_u6": False,
        "zones": [
            {"area": "Freising Zentrum", "lat": 48.4029, "lon": 11.7485, "radius_km": 2.8, "role": "City centre", "age": "20–60", "why": "Central adult catchment", "creative": "Award-winning immersive music event"},
            {"area": "Weihenstephan", "lat": 48.3983, "lon": 11.7285, "radius_km": 2.5, "role": "University", "age": "20–60", "why": "University and research audience", "creative": "Music + 360° visual experience"},
            {"area": "Lerchenfeld", "lat": 48.3945, "lon": 11.7790, "radius_km": 2.8, "role": "Residential", "age": "20–60", "why": "Residential catchment and local reach", "creative": "Four Tuesday nights + destination experience"},
        ],
    },
    "Ismaning": {
        "label": "Ismaning",
        "search_area": "Ismaning + Unterföhring",
        "center": {"lat": 48.2260, "lon": 11.6760},
        "show_u6": False,
        "zones": [
            {"area": "Ismaning Zentrum", "lat": 48.2260, "lon": 11.6760, "radius_km": 2.5, "role": "City centre", "age": "20–60", "why": "Local adult catchment close to Garching", "creative": "Award-winning immersive music event"},
            {"area": "Unterföhring", "lat": 48.1920, "lon": 11.6460, "radius_km": 2.5, "role": "Work / residential", "age": "20–60", "why": "Large workplace and residential catchment", "creative": "Music + 360° visual experience"},
            {"area": "Ismaning Nord", "lat": 48.2430, "lon": 11.6780, "radius_km": 2.3, "role": "North catchment", "age": "20–60", "why": "Closer northern catchment toward Garching", "creative": "Four Tuesday nights + easy regional access"},
        ],
    },
    "Unterschleißheim": {
        "label": "Unterschleißheim",
        "search_area": "Unterschleißheim + Oberschleißheim",
        "center": {"lat": 48.2800, "lon": 11.5760},
        "show_u6": False,
        "zones": [
            {"area": "Unterschleißheim Zentrum", "lat": 48.2800, "lon": 11.5760, "radius_km": 2.8, "role": "City centre", "age": "20–60", "why": "Central local catchment", "creative": "Award-winning immersive music event"},
            {"area": "Lohhof", "lat": 48.2855, "lon": 11.5840, "radius_km": 2.3, "role": "Residential", "age": "20–60", "why": "Residential and commuter catchment", "creative": "Music + 360° visual experience"},
            {"area": "Oberschleißheim", "lat": 48.2502, "lon": 11.5660, "radius_km": 2.8, "role": "Regional", "age": "20–60", "why": "Regional audience between Munich North and the venue", "creative": "Four Tuesday nights + destination experience"},
        ],
    },
    "Erding": {
        "label": "Erding",
        "search_area": "Erding",
        "center": {"lat": 48.3060, "lon": 11.9070},
        "show_u6": False,
        "zones": [
            {"area": "Erding Zentrum", "lat": 48.3060, "lon": 11.9070, "radius_km": 3.0, "role": "City centre", "age": "20–60", "why": "Central adult catchment", "creative": "Award-winning immersive music event"},
            {"area": "Altenerding", "lat": 48.2925, "lon": 11.9085, "radius_km": 2.6, "role": "Residential", "age": "20–60", "why": "Residential and commuter audience", "creative": "Music + 360° visual experience"},
            {"area": "Erding Nord", "lat": 48.3230, "lon": 11.9000, "radius_km": 2.8, "role": "North catchment", "age": "20–60", "why": "Northern regional catchment", "creative": "Four Tuesday nights + destination experience"},
        ],
    },
    "Dachau": {
        "label": "Dachau",
        "search_area": "Dachau + Karlsfeld",
        "center": {"lat": 48.2600, "lon": 11.4340},
        "show_u6": False,
        "zones": [
            {"area": "Dachau Zentrum", "lat": 48.2600, "lon": 11.4340, "radius_km": 3.0, "role": "City centre", "age": "20–60", "why": "Central adult catchment", "creative": "Award-winning immersive music event"},
            {"area": "Dachau Ost", "lat": 48.2580, "lon": 11.4550, "radius_km": 2.6, "role": "Residential", "age": "20–60", "why": "Eastern residential catchment", "creative": "Music + 360° visual experience"},
            {"area": "Karlsfeld", "lat": 48.2260, "lon": 11.4750, "radius_km": 2.8, "role": "Regional", "age": "20–60", "why": "Large regional catchment between Dachau and Munich", "creative": "Four Tuesday nights + destination experience"},
        ],
    },
}


def market_catalog(cfg: dict | None = None) -> dict:
    """Return built-in planning markets. Values are copied for safe mutation."""
    _ = cfg or load_config()
    return deepcopy(DEFAULT_MARKETS)


def default_market_key(cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    key = str(cfg.get("market_testing", {}).get("default_city", "Garching / Munich North"))
    return key if key in DEFAULT_MARKETS else "Garching / Munich North"


def custom_market(name: str, lat: float, lon: float, radius_km: float = 2.5) -> dict:
    """Create a neutral three-zone planning layout around a manually supplied centre."""
    name = (name or "Custom city").strip()
    lat = float(lat)
    lon = float(lon)
    radius_km = float(radius_km)
    return {
        "label": name,
        "search_area": name,
        "center": {"lat": lat, "lon": lon},
        "show_u6": False,
        "custom": True,
        "zones": [
            {"area": f"{name} · Centre", "lat": lat, "lon": lon, "radius_km": radius_km, "role": "Centre", "age": "20–60", "why": "Neutral custom-city centre test", "creative": "Award-winning immersive music event"},
            {"area": f"{name} · North", "lat": lat + 0.018, "lon": lon, "radius_km": radius_km, "role": "North", "age": "20–60", "why": "Neutral custom-city north test", "creative": "Music + 360° visual experience"},
            {"area": f"{name} · South", "lat": lat - 0.018, "lon": lon, "radius_km": radius_km, "role": "South", "age": "20–60", "why": "Neutral custom-city south test", "creative": "Four Tuesday nights + destination experience"},
        ],
    }


def get_market(key: str | None = None, cfg: dict | None = None) -> dict:
    catalog = market_catalog(cfg)
    chosen = key or default_market_key(cfg)
    return deepcopy(catalog.get(chosen, catalog[default_market_key(cfg)]))


def market_area_names(market: dict) -> list[str]:
    return [str(z["area"]) for z in market.get("zones", [])]
