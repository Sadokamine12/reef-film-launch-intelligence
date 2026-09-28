from __future__ import annotations

from datetime import date
import unittest

import pandas as pd

from launch_strategy import show_plan, target_tickets, today_decision
from project_config import load_config


class LaunchStrategyTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()

    def test_prelaunch_spend_is_zero(self):
        plan = show_plan(self.cfg, as_of=date(2026, 9, 28))
        self.assertTrue((plan["status"] == "PRE-LAUNCH").all())
        self.assertTrue((plan["daily_budget"] == 0).all())
        decision = today_decision(plan, self.cfg, as_of=date(2026, 9, 28))
        self.assertEqual(decision["budget"], 0)

    def test_target_curve_checkpoints(self):
        self.assertEqual(target_tickets(60, self.cfg), 8)
        self.assertEqual(target_tickets(30, self.cfg), 25)
        self.assertEqual(target_tickets(14, self.cfg), 55)
        self.assertEqual(target_tickets(7, self.cfg), 75)
        self.assertEqual(target_tickets(0, self.cfg), 98)

    def test_action_watch_ontrack_and_near_full(self):
        show_date = "2027-02-02"
        collected = "2027-01-19T08:00:00Z"  # 14 days before the show

        def plan_for(sold):
            frame = pd.DataFrame([{
                "show_date": show_date,
                "tickets_sold": sold,
                "collected_at": collected,
                "status": "ok",
            }])
            return show_plan(self.cfg, frame, as_of=date(2027, 1, 19)).iloc[0]

        self.assertEqual(plan_for(30)["status"], "ACTION")
        self.assertEqual(plan_for(48)["status"], "WATCH")
        self.assertEqual(plan_for(60)["status"], "ON TRACK")
        near_full = plan_for(96)
        self.assertEqual(near_full["status"], "NEAR FULL")
        self.assertEqual(int(near_full["daily_budget"]), 0)


if __name__ == "__main__":
    unittest.main()
