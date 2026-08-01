"""Metric derivation, especially the calendar-alignment traps.

These exist because both bugs they cover were real and were found only by
running against live filings: labels taken from the filer's fiscal calendar
while sorting used SEC's normalised one, and year-on-year computed by
positional offset. Tesla is missing CY2025Q4 from its frames (Q4 is folded into
the 10-K and never tagged as a discrete quarter), which made a positional
comparison span five quarters and report 46% growth instead of 25.5%.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ciel.model import Point, Series  # noqa: E402
from ciel.sources import xbrl_facts   # noqa: E402


def q(frame, val, accession="0000000000-00-000000"):
    return Point(end="", val=float(val), frame=frame, accession=accession)


class TestPointLabels(unittest.TestCase):
    def test_label_comes_from_calendar_frame_not_fiscal_period(self):
        point = Point(end="2026-03-31", val=1.0, fy=2027, fp="Q3", frame="CY2026Q1")
        self.assertEqual(point.label, "Q1 2026")
        self.assertEqual(point.calendar, (2026, 1))

    def test_instant_frame_strips_suffix(self):
        self.assertEqual(Point(end="", val=1, frame="CY2026Q1I").label, "Q1 2026")
        self.assertEqual(Point(end="", val=1, frame="CY2026Q1I").calendar, (2026, 1))

    def test_annual_frame(self):
        self.assertEqual(Point(end="", val=1, frame="CY2025").label, "2025")
        self.assertEqual(Point(end="", val=1, frame="CY2025").calendar, (2025, 0))

    def test_missing_frame_falls_back_without_raising(self):
        self.assertEqual(Point(end="2026-03-31", val=1, fy=2026, fp="Q1").label, "Q1 2026")
        self.assertIsNone(Point(end="2026-03-31", val=1).calendar)


class TestYearAgo(unittest.TestCase):
    def test_matches_same_quarter_across_a_gap(self):
        """The Tesla case: CY2025Q4 absent must not shift the comparison."""
        series = Series("Revenues", "USD", [
            q("CY2025Q1", 19335), q("CY2025Q2", 22496), q("CY2025Q3", 28095),
            q("CY2026Q1", 22387), q("CY2026Q2", 28236),
        ])
        latest, year_ago = series.year_ago()
        self.assertEqual(latest.frame, "CY2026Q2")
        self.assertEqual(year_ago.frame, "CY2025Q2")
        growth = (latest.val - year_ago.val) / year_ago.val
        self.assertAlmostEqual(growth, 0.2551, places=3)

    def test_returns_none_rather_than_guessing(self):
        series = Series("Revenues", "USD", [q("CY2026Q1", 100), q("CY2026Q2", 110)])
        latest, year_ago = series.year_ago()
        self.assertEqual(latest.frame, "CY2026Q2")
        self.assertIsNone(year_ago, "no same-quarter match should yield None, not a wrong one")

    def test_empty_series(self):
        self.assertEqual(Series("X", "USD", []).year_ago(), (None, None))


class TestDerivedMetrics(unittest.TestCase):
    def _series(self):
        return {
            "revenue": Series("Revenues", "USD", [
                q("CY2025Q1", 100), q("CY2025Q2", 110), q("CY2025Q3", 120),
                q("CY2026Q1", 130), q("CY2026Q2", 143),
            ]),
            "gross_profit": Series("GrossProfit", "USD", [
                q("CY2025Q1", 50), q("CY2025Q2", 55), q("CY2025Q3", 60),
                q("CY2026Q1", 70), q("CY2026Q2", 85.8),
            ]),
            "operating_cash_flow": Series("NetCash", "USD", [
                q("CY2025Q3", -5), q("CY2026Q1", -5), q("CY2026Q2", -5),
            ]),
            "cash": Series("Cash", "USD", [q("CY2026Q1I", 100), q("CY2026Q2I", 90)]),
            "assets": Series("Assets", "USD", [q("CY2026Q1I", 400), q("CY2026Q2I", 420)]),
            "equity": Series("Equity", "USD", [q("CY2026Q1I", 200), q("CY2026Q2I", 210)]),
        }

    def test_growth_uses_matching_quarter(self):
        m = xbrl_facts.derive_metrics(self._series())
        self.assertAlmostEqual(m["revenue_growth_yoy"], 0.30, places=6)
        self.assertEqual(m["revenue_growth_basis"], "Q2 2026 vs Q2 2025")

    def test_gross_margin_legs_come_from_the_same_period(self):
        m = xbrl_facts.derive_metrics(self._series())
        self.assertAlmostEqual(m["gross_margin"], 0.60, places=6)
        self.assertAlmostEqual(m["gross_margin_prior"], 0.50, places=6)
        self.assertAlmostEqual(m["gross_margin_trend"], 0.10, places=6)

    def test_runway_from_burn(self):
        m = xbrl_facts.derive_metrics(self._series())
        self.assertFalse(m["cash_flow_positive"])
        # 90 cash against 15 burn over the reported quarters -> 12 months.
        self.assertAlmostEqual(m["runway_months"], 90.0 / (15.0 / 12.0), places=3)

    def test_positive_cash_flow_reports_no_runway_pressure(self):
        series = self._series()
        series["operating_cash_flow"] = Series("NetCash", "USD", [
            q("CY2026Q1", 10), q("CY2026Q2", 12)])
        m = xbrl_facts.derive_metrics(series)
        self.assertTrue(m["cash_flow_positive"])
        self.assertEqual(m["runway_months"], 999.0)

    def test_negative_equity_flagged_not_silently_dropped(self):
        series = self._series()
        series["equity"] = Series("Equity", "USD", [q("CY2026Q2I", -50)])
        m = xbrl_facts.derive_metrics(series)
        self.assertTrue(m.get("negative_equity"))
        self.assertNotIn("debt_to_equity", m)

    def test_completeness_is_a_fraction_not_a_count(self):
        m = xbrl_facts.derive_metrics(self._series())
        self.assertGreater(m["field_completeness"], 0.0)
        self.assertLessEqual(m["field_completeness"], 1.0)

    def test_absent_data_yields_absent_metrics(self):
        m = xbrl_facts.derive_metrics({})
        self.assertNotIn("revenue_growth_yoy", m)
        self.assertNotIn("gross_margin", m)
        self.assertEqual(m["field_completeness"], 0.2)


class TestNormalise(unittest.TestCase):
    def test_latest_filing_wins_on_restatement(self):
        rows = [
            {"frame": "CY2026Q1", "val": 100, "filed": "2026-05-01", "accn": "old"},
            {"frame": "CY2026Q1", "val": 105, "filed": "2026-08-01", "accn": "new"},
        ]
        points = xbrl_facts._normalise(rows, instant=False)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].val, 105)
        self.assertEqual(points[0].accession, "new")

    def test_unframed_rows_are_ignored(self):
        rows = [{"val": 1, "filed": "2026-01-01"}, {"frame": "CY2026Q1", "val": 2, "filed": "2026-01-01"}]
        self.assertEqual(len(xbrl_facts._normalise(rows, instant=False)), 1)

    def test_instant_and_duration_do_not_mix(self):
        rows = [{"frame": "CY2026Q1I", "val": 1, "filed": "2026-01-01"}]
        self.assertEqual(len(xbrl_facts._normalise(rows, instant=False)), 0)
        self.assertEqual(len(xbrl_facts._normalise(rows, instant=True)), 1)


if __name__ == "__main__":
    unittest.main()
