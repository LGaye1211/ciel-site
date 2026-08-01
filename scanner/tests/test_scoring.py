"""Scoring, disqualification, the auto-writer and the rate limiter.

The load-bearing assertions here are the honesty ones: every contribution must
carry evidence, the bear case must never be empty, and generated triggers must
not already be firing against the data they were derived from.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from ciel.http import _Bucket                                  # noqa: E402
from ciel.model import Company, Point, Series                  # noqa: E402
from ciel.score import bearcase, disqualify, engine, signals, thesis, triggers  # noqa: E402
from ciel.sources import edgar_submissions as subs             # noqa: E402

CONFIG = os.path.join(os.path.dirname(HERE), "config")


def load(name):
    with open(os.path.join(CONFIG, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


M = 1_000_000.0


def q(frame, val):
    """Values are in millions, as real filings are - the revenue floor is $1m."""
    return Point(end="", val=float(val) * M, frame=frame, accession="0001234567-26-000001")


def healthy_company():
    c = Company(cik="1234567", name="Example Robotics Inc.", slug="example-robotics-234567")
    c.tickers = ["EXR"]
    c.exchanges = ["Nasdaq"]
    c.sic = "3559"
    c.sic_description = "Special Industry Machinery"
    c.country = "California"
    c.listed_years = 3.0
    c.annual_only = False
    c.description = "Designs and sells industrial robots to manufacturers."
    c.series = {
        "revenue": Series("Revenues", "USD", [
            q("CY2025Q1", 80), q("CY2025Q2", 90), q("CY2025Q3", 100),
            q("CY2026Q1", 104), q("CY2026Q2", 126)]),
        "gross_profit": Series("GrossProfit", "USD", [
            q("CY2025Q1", 40), q("CY2025Q2", 46), q("CY2025Q3", 52),
            q("CY2026Q1", 58), q("CY2026Q2", 76)]),
        "operating_income": Series("OperatingIncomeLoss", "USD", [
            q("CY2025Q2", -5), q("CY2026Q2", 4)]),
        "operating_cash_flow": Series("NetCash", "USD", [
            q("CY2025Q3", 6), q("CY2026Q1", 7), q("CY2026Q2", 9)]),
        "cash": Series("Cash", "USD", [q("CY2026Q2I", 300)]),
        "assets": Series("Assets", "USD", [q("CY2026Q2I", 600)]),
        "equity": Series("Equity", "USD", [q("CY2026Q2I", 450)]),
        "long_term_debt": Series("LongTermDebt", "USD", [q("CY2026Q2I", 40)]),
        "diluted_shares": Series("Shares", "shares", [
            q("CY2025Q2", 100), q("CY2026Q2", 102)]),
    }
    from ciel.sources import xbrl_facts
    c.metrics = xbrl_facts.derive_metrics(c.series)
    return c


class TestScoringContract(unittest.TestCase):
    def setUp(self):
        self.rubric = load("rubric.json")
        self.company = healthy_company()

    def test_dimension_weights_sum_to_100(self):
        total = sum(d["weight"] for d in self.rubric["dimensions"])
        self.assertEqual(total, 100, "rubric dimension weights must sum to 100")

    def test_signal_weights_within_each_dimension_sum_to_one(self):
        for dim in self.rubric["dimensions"]:
            total = sum(s["weight"] for s in dim["signals"])
            self.assertAlmostEqual(total, 1.0, places=6,
                                   msg="signal weights in '%s' must sum to 1" % dim["id"])

    def test_every_contribution_carries_evidence(self):
        """A number with no evidence is the failure mode this whole tool exists to avoid."""
        score = engine.evaluate(self.company, self.rubric)
        self.assertTrue(score.contributions)
        for c in score.contributions:
            self.assertTrue(c.evidence, "signal %s produced no evidence" % c.signal_id)
            for e in c.evidence:
                self.assertTrue(e.text.strip(), "empty evidence text on %s" % c.signal_id)

    def test_score_stays_within_range(self):
        score = engine.evaluate(self.company, self.rubric)
        self.assertGreater(score.total, 0)
        self.assertLessEqual(score.total, 100)

    def test_missing_signals_redistribute_rather_than_score_zero(self):
        """Absent is not bad. A company we know less about must not be punished
        as though we knew something bad about it."""
        rich = engine.evaluate(healthy_company(), self.rubric)

        sparse_company = healthy_company()
        del sparse_company.series["gross_profit"]
        from ciel.sources import xbrl_facts
        sparse_company.metrics = xbrl_facts.derive_metrics(sparse_company.series)
        sparse = engine.evaluate(sparse_company, self.rubric)

        self.assertGreater(sparse.dimensions["quality"], 0,
                           "a dimension with some signals present must not collapse to zero")
        self.assertLess(sparse.dimensions["coverage"], rich.dimensions["coverage"],
                        "less data must reduce the coverage dimension specifically")

    def test_scoring_is_deterministic(self):
        a = engine.evaluate(healthy_company(), self.rubric).total
        b = engine.evaluate(healthy_company(), self.rubric).total
        self.assertEqual(a, b)


class TestDisqualifiers(unittest.TestCase):
    def setUp(self):
        self.rubric = load("rubric.json")
        self.universe = load("universe.json")

    def test_healthy_company_survives(self):
        reasons = disqualify.check(healthy_company(), self.rubric, self.universe)
        self.assertEqual(reasons, [], "healthy fixture should not be eliminated: %s" % reasons)

    def test_short_runway_eliminates(self):
        c = healthy_company()
        c.metrics["runway_months"] = 4.0
        c.metrics["cash_flow_positive"] = False
        ids = [r["id"] for r in disqualify.check(c, self.rubric, self.universe)]
        self.assertIn("runway_under_12m", ids)

    def test_heavy_dilution_eliminates(self):
        c = healthy_company()
        c.metrics["dilution_yoy"] = 0.42
        ids = [r["id"] for r in disqualify.check(c, self.rubric, self.universe)]
        self.assertIn("dilution_over_25pct", ids)

    def test_stale_data_eliminates(self):
        """Found in a live run: TransMedics files on time, but its tagged series
        stops at Q3 2022, so the tool reported +349% growth from four-year-old
        figures as though it were current."""
        c = healthy_company()
        c.metrics["data_age_months"] = 44
        c.metrics["data_latest_period"] = "Q3 2022"
        reasons = disqualify.check(c, self.rubric, self.universe)
        ids = [r["id"] for r in reasons]
        self.assertIn("stale_data", ids)
        detail = [r["detail"] for r in reasons if r["id"] == "stale_data"][0]
        self.assertIn("Q3 2022", detail, "the reason must name the period it stopped at")

    def test_recent_data_survives(self):
        c = healthy_company()
        c.metrics["data_age_months"] = 4
        self.assertEqual(disqualify.check(c, self.rubric, self.universe), [])

    def test_annual_filers_get_a_longer_window(self):
        c = healthy_company()
        c.annual_only = True
        c.metrics["data_age_months"] = 14
        c.metrics["data_latest_period"] = "2025"
        ids = [r["id"] for r in disqualify.check(c, self.rubric, self.universe)]
        self.assertNotIn("stale_data", ids,
                         "a 20-F filer reporting annually is not stale at 14 months")

    def test_gapped_series_eliminates(self):
        c = healthy_company()
        c.metrics["series_density"] = 0.35
        ids = [r["id"] for r in disqualify.check(c, self.rubric, self.universe)]
        self.assertIn("gapped_series", ids)

    def test_nanocap_revenue_floor(self):
        c = healthy_company()
        c.metrics["revenue_ttm"] = 4_480_379.0
        ids = [r["id"] for r in disqualify.check(c, self.rubric, self.universe)]
        self.assertIn("no_revenue", ids,
                      "sub-$10m revenue is a nanocap, too thin to enter or leave")

    def test_going_concern_eliminates(self):
        c = healthy_company()
        c.metrics["going_concern"] = True
        ids = [r["id"] for r in disqualify.check(c, self.rubric, self.universe)]
        self.assertIn("going_concern", ids)

    def test_leveraged_instrument_eliminates(self):
        c = healthy_company()
        c.is_leveraged = True
        ids = [r["id"] for r in disqualify.check(c, self.rubric, self.universe)]
        self.assertIn("leveraged_instrument", ids)

    def test_every_reason_explains_itself(self):
        c = healthy_company()
        c.metrics["runway_months"] = 3.0
        c.metrics["cash_flow_positive"] = False
        for reason in disqualify.check(c, self.rubric, self.universe):
            self.assertTrue(reason["detail"].strip())
            self.assertGreater(len(reason["detail"]), 30,
                               "'%s eliminated' with no explanation is just a number" % reason["id"])


class TestTeamEvidence(unittest.TestCase):
    """Found in a live run: dual-class structures reported 100% insider
    ownership, and a company with one usable team signal redistributed the
    dimension onto it and scored 30/30 on the thing the charter cares most
    about."""

    def setUp(self):
        self.rubric = load("rubric.json")

    def _team_score(self, extra):
        c = healthy_company()
        c.metrics.update(extra)
        engine.evaluate(c, self.rubric)
        return c.score.dimensions["team"]

    def test_thin_evidence_cannot_max_the_dimension(self):
        thin = self._team_score({"insider_filings_read": 1, "insider_count": 1,
                                 "insider_selling": 0.0})
        rich = self._team_score({"insider_filings_read": 14, "insider_count": 8,
                                 "insider_selling": 0.0, "insider_ownership": 0.15})
        self.assertLess(thin, rich)
        self.assertLess(thin, 30.0 * 0.7,
                        "one weak signal must not reach near-maximum on team")

    def test_implausible_ownership_is_not_scored(self):
        scored = self._team_score({"insider_filings_read": 10, "insider_count": 5,
                                   "insider_ownership_unreliable": 1.0})
        credible = self._team_score({"insider_filings_read": 10, "insider_count": 5,
                                     "insider_ownership": 0.30})
        self.assertLess(scored, credible,
                        "a dual-class artefact must not outscore real alignment")

    def test_evidence_note_explains_the_exclusion(self):
        c = healthy_company()
        c.metrics.update({"insider_filings_read": 6, "insider_count": 4,
                          "insider_ownership_unreliable": 1.4})
        _raw, _scaled, evidence = signals.REGISTRY["team_evidence"](c, c.metrics)
        self.assertIn("share class", evidence[0].text)


class TestNameHeuristics(unittest.TestCase):
    def setUp(self):
        self.universe = load("universe.json")

    def _company(self, name, category=""):
        c = Company(cik="1", name=name)
        c.entity_category = category
        return c

    def test_spac_and_trust_names_flagged(self):
        for name in ("Northern Star Acquisition Corp", "Widget Royalty Trust",
                     "Generic Blank Check Co"):
            self.assertTrue(subs.looks_like_shell(self._company(name), self.universe), name)

    def test_operating_companies_not_flagged(self):
        for name in ("Example Robotics Inc.", "Oscar Health, Inc.", "Chewy, Inc.",
                     "Vertiv Holdings Co"):
            self.assertFalse(subs.looks_like_shell(self._company(name), self.universe), name)

    def test_leveraged_products_flagged(self):
        self.assertTrue(subs.looks_leveraged(self._company("ProShares Ultra Bloomberg"), self.universe))
        self.assertFalse(subs.looks_leveraged(self._company("Example Robotics Inc."), self.universe))

    def test_slug_is_stable_and_url_safe(self):
        slug = subs.make_slug("Example Robotics, Inc.", "1234567")
        self.assertEqual(slug, subs.make_slug("Example Robotics, Inc.", "1234567"))
        self.assertRegex(slug, r"^[a-z0-9-]+$")


class TestAutoWriter(unittest.TestCase):
    def test_bear_case_is_never_empty(self):
        """If nothing negative is found, that is a generator bug rather than a
        clean company. A tool that only finds reasons to buy is worse than none."""
        for company in (healthy_company(), Company(cik="9", name="Bare Co")):
            if not company.metrics:
                company.metrics = {}
            bear = bearcase.build(company)
            self.assertTrue(bear, "bear case empty for %s" % company.name)

    def test_generated_sentences_carry_a_source(self):
        c = healthy_company()
        built = thesis.build(c)
        built["bear"] = bearcase.build(c)
        for item in built["bull"] + built["bear"]:
            self.assertTrue(item["text"].strip())
            self.assertIn("source_url", item, "every generated claim needs a link: %s" % item["text"])

    def test_summary_is_three_sentences(self):
        summary = thesis.build_summary(healthy_company())
        self.assertEqual(len(summary["sentences"]), 3,
                         "charter rule 7 asks for three sentences")
        for sentence in summary["sentences"]:
            self.assertTrue(sentence.strip().endswith("."))

    def test_summary_flags_itself_as_generated(self):
        summary = thesis.build_summary(healthy_company())
        self.assertTrue(summary["generated"])
        self.assertIn("your own words", summary["note"])

    def test_no_figure_is_invented(self):
        """A company with no financials must not produce numeric claims."""
        c = Company(cik="9", name="Bare Co")
        c.metrics = {}
        built = thesis.build(c)
        self.assertEqual(built["bull"], [])


class TestTriggers(unittest.TestCase):
    def test_generated_triggers_are_not_already_firing(self):
        """Thresholds derive from the company's own current figures, so a fresh
        trigger firing immediately means the calibration is wrong."""
        c = healthy_company()
        for trigger in triggers.build(c):
            self.assertFalse(trigger["fired"],
                             "trigger '%s' fires against the data it came from" % trigger["id"])

    def test_every_trigger_is_machine_checkable(self):
        for trigger in triggers.build(healthy_company()):
            self.assertIn("metric", trigger)
            self.assertIn(trigger["comparison"], ("below", "above", "is_true"))
            self.assertIsNotNone(trigger["threshold"])

    def test_triggers_fire_on_a_deteriorating_series(self):
        c = healthy_company()
        armed = triggers.build(c)
        worse = dict(c.metrics)
        worse["gross_margin"] = 0.10
        worse["revenue_growth_yoy"] = -0.40
        worse["runway_months"] = 5.0
        worse["dilution_yoy"] = 0.60
        fired = triggers.evaluate(armed, worse)
        self.assertTrue(fired)
        ids = [t["id"] for t in fired]
        self.assertIn("gross_margin_floor", ids)
        self.assertIn("growth_floor", ids)

    def test_going_concern_trigger_always_present(self):
        ids = [t["id"] for t in triggers.build(healthy_company())]
        self.assertIn("going_concern", ids)

    def test_missing_metric_does_not_fire(self):
        armed = triggers.build(healthy_company())
        fired = triggers.evaluate(armed, {})
        self.assertEqual(fired, [], "absent data must not be read as a breach")


class TestRateLimit(unittest.TestCase):
    """Getting IP-banned by the SEC is the worst operational outcome available,
    so the bucket is verified against a fake clock rather than trusted."""

    def test_never_exceeds_budget(self):
        now = [0.0]
        def clock():
            return now[0]
        def sleep(seconds):
            now[0] += seconds

        bucket = _Bucket(8.0, 1.0, clock, sleep)
        for _ in range(8):
            bucket.take()
        self.assertEqual(now[0], 0.0, "the first burst should not need to wait")

        bucket.take()
        self.assertGreater(now[0], 0.0, "the ninth request in a second must wait")

        now[0] = 0.0
        bucket = _Bucket(8.0, 1.0, clock, sleep)
        for _ in range(80):
            bucket.take()
        self.assertGreaterEqual(now[0], 8.9, "80 requests at 8/s must take about 9 seconds")

    def test_companies_house_window(self):
        now = [0.0]
        bucket = _Bucket(540.0, 300.0, lambda: now[0], lambda s: now.__setitem__(0, now[0] + s))
        for _ in range(541):
            bucket.take()
        self.assertGreater(now[0], 0.0, "the 541st call in five minutes must wait")


if __name__ == "__main__":
    unittest.main()
