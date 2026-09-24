from __future__ import annotations

import ast
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from campaign_lab import import_campaign_csv, validate_campaign_rows
from data_contracts import canonical_booking_id, clean_eso_snapshots
from eso_baseline import fit_empirical_sales_curve
from eso_sales_tracker import is_cookie_privacy_only, parse_available_seats, upsert_daily_snapshots
from lightweight_ml import fit_bootstrap_ridge_ensemble, LightweightEnsemble
from project_config import load_config, flat_context
from training_engine import _group_folds, generate_active_learning_plan
from advanced_ml import optimize_budget, per_show_forecast
from ad_targeting_map import planned_zones
from experiment_protocol import build_experiment_plan
from market_context import market_catalog, custom_market, market_prediction_context
from model_quality import confidence_summary
from ui import editing_enabled


class DataTests(unittest.TestCase):
    def test_hosted_view_only_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(editing_enabled())
        with patch.dict(os.environ, {"REEF_ENABLE_EDITING": "1"}):
            self.assertTrue(editing_enabled())

    def test_canonical_language_urls(self):
        self.assertEqual(canonical_booking_id("https://supernova.eso.org/germany/programme/booking/ABC12/?lang=de"), "abc12")
        self.assertEqual(canonical_booking_id("https://supernova.eso.org/programme/booking/ABC12/?lang=en"), "abc12")

    def test_cookie_rejection_and_seats(self):
        self.assertTrue(is_cookie_privacy_only("<html><title>Was sind Cookies?</title><h1>Was sind Cookies?</h1></html>"))
        self.assertEqual(parse_available_seats("<p>Available seats: 53/109</p>"), (53, 109))

    def test_canonical_day_update(self):
        base = {"programme_title": "Dark Universe", "show_datetime_local": "2027-02-02 19:00", "capacity": 109, "source_type": "booking_page", "status": "ok", "days_to_event": 30}
        a = {**base, "collected_at_utc": "2027-01-01T09:00:00Z", "programme_url": "https://supernova.eso.org/programme/booking/abc12/?lang=en", "available_seats": 80, "tickets_sold_so_far": 29}
        b = {**a, "collected_at_utc": "2027-01-01T11:00:00Z", "programme_url": "https://supernova.eso.org/germany/programme/booking/abc12/?lang=de", "available_seats": 79, "tickets_sold_so_far": 30}
        c = {**b, "collected_at_utc": "2027-01-02T11:00:00Z", "days_to_event": 29}
        clean = clean_eso_snapshots(pd.DataFrame([a, b, c]))
        self.assertEqual(len(clean), 2)
        self.assertEqual(clean.sort_values("snapshot_day")["available_seats"].tolist(), [79, 79])

    def test_tracker_same_day_replace_next_day_append(self):
        path = Path("tests/tracker_snapshots.csv")
        row = {"collected_at_utc": "2027-01-01T08:00:00Z", "programme_title": "Dark Universe", "show_datetime_local": "2027-02-02 19:00", "programme_url": "https://supernova.eso.org/programme/booking/abc12/", "available_seats": 80, "capacity": 109, "tickets_sold_so_far": 29, "days_to_event": 32, "source_type": "booking_page", "status": "ok"}
        try:
            with patch("eso_sales_tracker.BASELINE_OUT", path):
                self.assertEqual(upsert_daily_snapshots([row])[0], 1)
                changed = {**row, "collected_at_utc": "2027-01-01T10:00:00Z", "available_seats": 79, "tickets_sold_so_far": 30}
                self.assertEqual(upsert_daily_snapshots([changed])[1], 1)
                following = {**changed, "collected_at_utc": "2027-01-02T10:00:00Z", "days_to_event": 31}
                self.assertEqual(upsert_daily_snapshots([following])[0], 1)
            self.assertEqual(len(pd.read_csv(path)), 2)
        finally:
            path.unlink(missing_ok=True)

    def test_empirical_monotonic(self):
        frame = pd.DataFrame({"days_to_event": [30, 30, 20, 20, 10, 10], "sold_fraction": [.1, .2, .25, .3, .45, .5], "show_key": list("aabbcc")})
        curve, stats = fit_empirical_sales_curve(frame)
        self.assertFalse(curve.empty)
        self.assertTrue(np.all(np.diff(curve["base_sold_pct"]) >= -1e-9))

    def test_grouped_folds(self):
        groups = pd.Series(["a", "a", "b", "b", "c", "c", "d", "d", "e", "e", "f", "f"])
        for train, test in _group_folds(groups, 3, 41):
            self.assertFalse(set(groups.iloc[train]) & set(groups.iloc[test]))

    def test_model_json_roundtrip(self):
        frame = pd.DataFrame({"days_to_event": [1, 2, 3, 4, 5, 6, 7, 8]})
        target = pd.Series([10., 12., 14., 16., 18., 20., 22., 24.])
        model = fit_bootstrap_ridge_ensemble(frame, target, ["days_to_event"], [], "tickets", seed=5, n_models=3)
        path = Path("tests/model_roundtrip.json")
        try:
            model.save(path)
            np.testing.assert_allclose(model.predict(frame), LightweightEnsemble.load(path).predict(frame))
        finally:
            path.unlink(missing_ok=True)

    def test_campaign_rejects_ambiguous_and_fake_labels(self):
        row = {"date": "2027-01-10", "channel": "Meta", "area": "Garching", "age_band": "20-60", "creative": "A", "spend_eur": 10, "impressions": 100, "clicks": 200}
        self.assertTrue(validate_campaign_rows(pd.DataFrame([row])))
        row["clicks"] = 5
        row["incremental_tickets_estimate"] = 3
        self.assertTrue(validate_campaign_rows(pd.DataFrame([row])))
        self.assertTrue(validate_campaign_rows(pd.DataFrame([row])))

    def test_budget_and_plan(self):
        cfg = load_config()
        path = Path("tests/plan_generated.csv")
        try:
            plan = generate_active_learning_plan(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(plan["planned_spend_eur"].sum() + cfg["marketing"]["scale_reserve_eur"], 500)
        allocation = optimize_budget(500, increment=25, max_cell_share=.4)
        self.assertLessEqual(allocation["budget_eur"].sum(), 500)
        self.assertTrue((allocation["budget_eur"] <= 200).all())
        zones, meta = planned_zones()
        self.assertEqual(int(zones["budget_eur"].sum()), 90)
        self.assertEqual(sorted(round(float(x)) for x in zones["budget_eur"].tolist()), [30, 30, 30])
        self.assertEqual(meta["geo_budget"] + meta["later_tests"] + meta["search_budget"] + meta["scale_reserve"], 500)
        confidence = confidence_summary({"unique_shows": 13, "repeated_shows": 13, "lead_min": 17}, {"mae": 17}, {"level": "E"})
        self.assertEqual(confidence["resolution_final"], "VERY LOW")

    def test_all_market_presets_keep_budget_and_three_zones(self):
        for name, market in market_catalog().items():
            plan = build_experiment_plan(market)
            self.assertEqual(plan["planned_spend_eur"].sum(), 240, name)
            wave1 = plan[plan["wave"].eq("Geo + creative")]
            self.assertEqual(wave1["area"].nunique(), 3, name)
            self.assertEqual(len(wave1), 6, name)
            self.assertTrue(wave1["city"].eq(market["label"]).all(), name)
            zones, meta = planned_zones(market=market)
            self.assertEqual(len(zones), 3, name)
            self.assertAlmostEqual(float(zones["budget_eur"].sum()), 90.0, places=6)
            self.assertEqual(meta["market_city"], market["label"])

        custom = custom_market("Teststadt", 48.1, 11.5, 3.0)
        plan = build_experiment_plan(custom)
        self.assertEqual(plan[plan["wave"].eq("Geo + creative")]["area"].nunique(), 3)
        self.assertTrue(plan["city"].eq("Teststadt").all())

    def test_city_prediction_prior_changes_planning_lift(self):
        markets = market_catalog()
        local = markets["Garching / Munich North"]
        freising = markets["Freising"]
        local_meta = market_prediction_context(local)
        freising_meta = market_prediction_context(freising)
        self.assertLess(local_meta["distance_to_venue_km"], freising_meta["distance_to_venue_km"])
        self.assertGreater(local_meta["scenario_factor"], freising_meta["scenario_factor"])
        self.assertGreaterEqual(freising_meta["scenario_factor"], 0.55)
        self.assertLessEqual(local_meta["scenario_factor"], 1.05)

        local_alloc = optimize_budget(90, market=local)
        freising_alloc = optimize_budget(90, market=freising)
        self.assertAlmostEqual(float(local_alloc["budget_eur"].sum()), 90.0, places=6)
        self.assertAlmostEqual(float(freising_alloc["budget_eur"].sum()), 90.0, places=6)
        self.assertGreater(
            float(local_alloc["expected_extra_tickets"].sum()),
            float(freising_alloc["expected_extra_tickets"].sum()),
        )

    def test_screening_forecast_is_differentiated_and_preserves_total(self):
        cfg = load_config()
        flat = flat_context(cfg)
        self.assertIsInstance(flat.get("venue"), str)  # regression: hosted app uses this flattened shape
        sim = pd.DataFrame({"total_tickets": [196, 206, 216, 206, 206]})
        shows = per_show_forecast(sim, flat)
        self.assertEqual(len(shows), 4)
        self.assertEqual(int(shows["base"].sum()), 206)
        self.assertGreater(shows["base"].nunique(), 1)
        self.assertEqual(shows["scenario_index"].tolist(), [96, 92, 108, 104])
        self.assertTrue((shows["low"] <= shows["base"]).all())
        self.assertTrue((shows["base"] <= shows["high"]).all())

    def test_manager_accessibility_band_and_market_evidence_template(self):
        markets = market_catalog()
        for market in markets.values():
            meta = market_prediction_context(market)
            self.assertIn(meta["accessibility"], {"HIGH", "MEDIUM", "LOW"})
            self.assertGreater(meta["distance_to_venue_km"], -0.1)
        evidence = pd.read_csv("data/market_evidence.csv")
        self.assertTrue({"city", "adult_population_20_60", "avg_travel_time_min", "meta_reachable_audience", "google_search_index", "eso_visitor_origin_share"}.issubset(evidence.columns))
        self.assertEqual(set(markets.keys()), set(evidence["city"]))

    def test_no_sklearn_import_and_page_syntax(self):
        for path in [*Path(".").glob("*.py"), *Path("pages").glob("*.py")]:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(any(a.name.startswith("sklearn") for a in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith("sklearn"))


if __name__ == "__main__":
    unittest.main()
