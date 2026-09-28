from __future__ import annotations

from pathlib import Path
import re
import unittest


class StreamlitPageRegistryTests(unittest.TestCase):
    def test_page_routes_are_unique(self):
        pages = Path("pages")
        routes: dict[str, list[str]] = {}
        for path in sorted(pages.glob("*.py")):
            route = re.sub(r"^\d+_", "", path.stem)
            routes.setdefault(route, []).append(path.name)

        duplicates = {route: files for route, files in routes.items() if len(files) > 1}
        self.assertEqual(
            duplicates,
            {},
            f"Duplicate Streamlit page route(s): {duplicates}. "
            "Files with different numeric prefixes can still resolve to the same URL.",
        )

    def test_management_pages_exist(self):
        required = {
            "1_Sales_Plan.py",
            "2_Where_to_Advertise.py",
            "3_Marketing_Plan.py",
            "4_Creatives.py",
            "6_Reports.py",
            "9_Settings.py",
        }
        existing = {p.name for p in Path("pages").glob("*.py")}
        self.assertTrue(required.issubset(existing), required - existing)

    def test_sidebar_page_links_exist(self):
        ui_source = Path("ui.py").read_text(encoding="utf-8")
        targets = re.findall(r'st\\.page_link\\("([^"]+)"', ui_source)
        self.assertTrue(targets, "No sidebar page links found in ui.py")
        missing = [target for target in targets if not Path(target).exists()]
        self.assertEqual(
            missing,
            [],
            f"Sidebar contains stale Streamlit page link(s): {missing}",
        )


if __name__ == "__main__":
    unittest.main()
