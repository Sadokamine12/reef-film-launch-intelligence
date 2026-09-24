"""Blocking and advisory checks for a portable Windows installation."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
import sys

import pandas as pd

from campaign_lab import attribution_readiness, campaign_summary, validate_campaign_rows
from data_contracts import CAMPAIGN_COLUMNS, ESO_SNAPSHOT_COLUMNS, canonical_booking_id, read_csv_safe
from eso_baseline import fit_empirical_sales_curve, load_validated_snapshots
from model_quality import load_status
from project_config import load_config, total_capacity
from market_context import market_catalog
from experiment_protocol import build_experiment_plan


def run_checks() -> list[dict]:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str, level: str = "error") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail), "level": level})

    add("Config file", Path("config/project.json").exists(), "config/project.json")
    cfg = load_config()
    dates = cfg["screenings"]["dates"]
    expected = ["2027-02-02", "2027-02-09", "2027-02-16", "2027-02-23"]
    valid_dates = dates == expected
    try:
        valid_dates &= all(date.fromisoformat(d).weekday() == 1 for d in dates)
    except ValueError:
        valid_dates = False
    add("Screenings and capacity", valid_dates and total_capacity(cfg) == 436, f"{len(dates)} dates; {total_capacity(cfg)} seats")
    marketing = cfg["marketing"]
    budget = float(marketing["total_budget_eur"])
    learning = float(marketing["experiment_budget_eur"])
    reserve = float(marketing["scale_reserve_eur"])
    add("Budget", budget == 500 and learning + reserve == budget, f"EUR {learning:g} learning + EUR {reserve:g} reserve = EUR {budget:g}")
    markets = market_catalog(cfg)
    market_ok = len(markets) >= 3 and all(len(m.get("zones", [])) >= 3 for m in markets.values())
    add("Target markets", market_ok, f"{len(markets)} preset cities; custom city supported", "warning")
    folders = ["config", "data", "models", "pages", "docs"]
    add("Folders", all(Path(p).is_dir() for p in folders), ", ".join(folders))

    raw = read_csv_safe("data/eso_comparable_snapshots.csv")
    add("ESO schema", set(ESO_SNAPSHOT_COLUMNS).issubset(raw.columns), f"{len(raw)} raw rows")
    snaps = load_validated_snapshots()
    rejected = len(raw) - len(snaps)
    add("Canonical booking/day", rejected == 0 and not snaps.duplicated(["show_key", "snapshot_day"]).any(), f"{len(snaps)} valid; {rejected} invalid or duplicate", "warning")
    latest = snaps["collected_at_dt"].max() if not snaps.empty else pd.NaT
    stale_days = (pd.Timestamp.now(tz="UTC") - latest).days if pd.notna(latest) else None
    add("ESO freshness", stale_days is not None and stale_days <= 7, f"Newest valid observation {stale_days if stale_days is not None else 'n/a'} day(s) old", "warning")
    seats_ok = snaps.empty or (snaps["booking_id"].ne("").all() and snaps["capacity"].eq(109).all() and snaps["tickets_sold_so_far"].eq(snaps["capacity"] - snaps["available_seats"]).all())
    add("Booking IDs and seats", seats_ok, "Booking-only, 109 seats, sold count consistent", "warning")
    cookie = snaps["programme_title"].astype(str).str.contains("cookie|weitere information|kategorien der von uns", case=False, regex=True).any() if not snaps.empty else False
    add("Privacy pages", not cookie, "No cookie titles in training data")
    curve, stats = fit_empirical_sales_curve(snaps)
    add("Empirical baseline", not curve.empty, f"{stats.get('unique_shows', 0)} shows; nearest observed lead {stats.get('min_days_to_event', 'n/a')} days", "warning")

    campaign = read_csv_safe("data/campaign_history.csv")
    add("Campaign schema", set(CAMPAIGN_COLUMNS).issubset(campaign.columns) and (campaign.empty or not validate_campaign_rows(campaign)), f"{len(campaign)} rows")
    summary = campaign_summary()
    add("Campaign labels", summary["engagement_rows"] > 0, f"{summary['engagement_rows']} engagement rows; {summary['verified_ticket_rows']} tracked-ticket rows", "warning")
    attr = attribution_readiness()
    add("Attribution", attr["verified_ticket_rows"] > 0, "Level E: aggregate seat movement only" if attr["verified_ticket_rows"] == 0 else attr["label"], "warning")
    urls = cfg.get("tracking", {}).get("resolution_booking_urls", [])
    ids = [canonical_booking_id(u if isinstance(u, str) else u.get("url", "")) for u in urls]
    add("Resolution URLs", len(ids) == 4 and len(set(ids)) == 4 and all(ids), f"{len(ids)} configured", "warning")
    tracking = cfg.get("tracking", {})
    add("UTM structure", bool(tracking.get("utm_source_pattern") and tracking.get("utm_campaign_pattern")), "Campaign/source patterns", "warning")

    plan = read_csv_safe("data/experiment_plan.csv")
    spend = pd.to_numeric(plan.get("planned_spend_eur", pd.Series(dtype=float)), errors="coerce").sum()
    dynamic_plans_ok = True
    for market in markets.values():
        generated = build_experiment_plan(market)
        dynamic_plans_ok &= len(generated) >= 13 and float(generated["planned_spend_eur"].sum()) == learning
    add("Experiment plan", len(plan) >= 13 and spend == learning and "step" in plan and plan["step"].is_unique and dynamic_plans_ok, f"EUR {spend:g} test spend + EUR {reserve:g} reserve; city plans valid")

    status = load_status()
    add("Training status", bool(status), status.get("backend", "Run train_models.py"), "warning")
    for item in status.get("models", []):
        add(item.get("name", "Model"), item.get("status") in {"trained", "trained_low_confidence", "collecting", "waiting"}, f"{item.get('status')}; {item.get('rows')} rows; operational={item.get('operational')}", "warning")
        if item.get("model_path"):
            from lightweight_ml import LightweightEnsemble
            try:
                model_path = Path(str(item["model_path"]).replace("\\", "/"))
                model = LightweightEnsemble.load(model_path)
                intact = bool(model.weights and len(model.weights[0]) == len(model.state.feature_names))
            except Exception:
                intact = False
            add(item["name"] + " JSON", intact, str(item["model_path"]))

    page_paths = [Path("Executive_Forecast.py"), *Path("pages").glob("*.py")]
    errors = []
    for path in page_paths:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            errors.append(f"{path}: {exc}")
    add("Streamlit pages", len(page_paths) >= 8 and not errors, "; ".join(errors) if errors else f"{len(page_paths)} pages parse")
    bad_imports = []
    for path in [*Path(".").glob("*.py"), *Path("pages").glob("*.py")]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                bad_imports.extend(a.name for a in node.names if a.name.startswith(("sklearn", "pytrends")))
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(("sklearn", "pytrends")):
                bad_imports.append(node.module)
    req = Path("requirements.txt").read_text(encoding="utf-8")
    add("Windows dependencies", "scikit-learn" not in req.lower() and "pytrends" not in req.lower() and not bad_imports, "No sklearn or pytrends runtime dependency")
    return checks


def main() -> None:
    checks = run_checks()
    print("REEF project doctor")
    for item in checks:
        mark = "PASS" if item["ok"] else "WARNING" if item["level"] == "warning" else "FAIL"
        print(f"{mark}: {item['check']} - {item['detail']}")
    failures = sum(not item["ok"] and item["level"] == "error" for item in checks)
    print(f"Result: {failures} blocking failures")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
