"""Tests for landed_cost.py. Run from shop/economics:  python -m unittest -v"""

import io
import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import landed_cost as lc  # noqa: E402

D = Decimal


def row(**overrides):
    base = {
        "name": "t",
        "sale_price": "100",
        "doba_cost": "30",
        "doba_shipping": "10",
        "us_stock": "yes",
        "ship_days": "4",
        "supplier_score": "4.6",
        "category_flag": "",
    }
    base.update(overrides)
    return base


A = lc.Assumptions()


class MoneyMath(unittest.TestCase):
    def test_known_values(self):
        # 100 - 40 - 1.20 (doba 3% of 40) - 3.20 (2.9% + 0.30) - 2.00 (fx) - 15.00 (refunds)
        r = lc.evaluate(row(), A)
        self.assertEqual(r.verdict, "PASS")
        self.assertEqual(r.net, D("38.6"))
        self.assertEqual(r.margin_pct, D("60"))
        self.assertEqual(r.product_cost, D("40"))

    def test_refund_allowance_moves_net(self):
        a = lc.Assumptions(refund_pct=D("0"))
        self.assertEqual(lc.evaluate(row(), a).net, D("53.6"))

    def test_gateway_extra_reduces_net(self):
        a = lc.Assumptions(gateway_extra_pct=D("2"))
        self.assertEqual(lc.evaluate(row(), a).net, D("36.6"))

    def test_currency_symbols_and_commas(self):
        self.assertEqual(lc.parse_money("$1,299.50", "x"), D("1299.50"))


class Gates(unittest.TestCase):
    def test_margin_boundary_passes_at_exactly_forty(self):
        r = lc.evaluate(row(doba_cost="50", doba_shipping="10"), A)
        self.assertEqual(r.margin_pct, D("40"))
        self.assertEqual(r.verdict, "PASS")

    def test_margin_just_under_forty_fails(self):
        r = lc.evaluate(row(doba_cost="50.01", doba_shipping="10"), A)
        self.assertEqual(r.verdict, "FAIL")
        self.assertTrue(any("gross margin" in why for why in r.reasons))

    def test_low_price_fails_net_and_margin(self):
        # 20 - 13 - 0.39 - 0.88 - 0.40 - 3.00 = 2.33, margin 35%
        r = lc.evaluate(row(sale_price="20", doba_cost="8", doba_shipping="5"), A)
        self.assertEqual(r.verdict, "FAIL")
        self.assertEqual(r.net, D("2.33"))
        self.assertTrue(any("net" in why for why in r.reasons))
        self.assertTrue(any("gross margin" in why for why in r.reasons))

    def test_net_boundary(self):
        # With zero percent fees: sale 20 on 12 landed gives net exactly 8 and margin exactly 40%.
        a = lc.Assumptions(
            pay_pct=D("0"), pay_fixed=D("0"), fx_pct=D("0"), doba_card_pct=D("0"), refund_pct=D("0")
        )
        ok = lc.evaluate(row(sale_price="20", doba_cost="8", doba_shipping="4"), a)
        self.assertEqual(ok.net, D("8"))
        self.assertEqual(ok.margin_pct, D("40"))
        self.assertEqual(ok.verdict, "PASS")
        low = lc.evaluate(row(sale_price="19.99", doba_cost="8", doba_shipping="4"), a)
        self.assertEqual(low.verdict, "FAIL")
        self.assertTrue(any("net" in why for why in low.reasons))


class HardRules(unittest.TestCase):
    def test_regulated_category_rejected(self):
        r = lc.evaluate(row(category_flag="supplement"), A)
        self.assertEqual(r.verdict, "REJECT")
        self.assertTrue(any("category" in why for why in r.reasons))

    def test_none_flag_is_not_a_flag(self):
        self.assertEqual(lc.evaluate(row(category_flag="none"), A).verdict, "PASS")

    def test_not_us_stocked_rejected(self):
        self.assertEqual(lc.evaluate(row(us_stock="no"), A).verdict, "REJECT")

    def test_ship_days_boundary(self):
        self.assertEqual(lc.evaluate(row(ship_days="7"), A).verdict, "PASS")
        self.assertEqual(lc.evaluate(row(ship_days="8"), A).verdict, "REJECT")

    def test_supplier_score_boundary(self):
        self.assertEqual(lc.evaluate(row(supplier_score="4.0"), A).verdict, "PASS")
        self.assertEqual(lc.evaluate(row(supplier_score="3.9"), A).verdict, "REJECT")

    def test_reject_beats_fail_and_keeps_both_reasons(self):
        r = lc.evaluate(row(sale_price="20", doba_cost="8", doba_shipping="5", category_flag="cosmetic"), A)
        self.assertEqual(r.verdict, "REJECT")
        self.assertTrue(any("category" in why for why in r.reasons))
        self.assertTrue(any("net" in why for why in r.reasons))


class Inputs(unittest.TestCase):
    def test_missing_money_is_unknown(self):
        r = lc.evaluate(row(doba_cost=""), A)
        self.assertEqual(r.verdict, "UNKNOWN")
        self.assertIn("missing: doba_cost", r.reasons[0])

    def test_bad_number_is_unknown(self):
        self.assertEqual(lc.evaluate(row(sale_price="abc"), A).verdict, "UNKNOWN")

    def test_negative_number_is_unknown(self):
        self.assertEqual(lc.evaluate(row(doba_shipping="-1"), A).verdict, "UNKNOWN")

    def test_zero_sale_price_is_unknown(self):
        self.assertEqual(lc.evaluate(row(sale_price="0"), A).verdict, "UNKNOWN")

    def test_bad_yes_no_is_unknown(self):
        self.assertEqual(lc.evaluate(row(us_stock="maybe"), A).verdict, "UNKNOWN")

    def test_blank_check_holds(self):
        r = lc.evaluate(row(ship_days=""), A)
        self.assertEqual(r.verdict, "HOLD")
        self.assertEqual(r.reasons, ["unchecked: ship_days"])

    def test_several_blank_checks_listed(self):
        r = lc.evaluate(row(us_stock="", supplier_score=""), A)
        self.assertEqual(r.verdict, "HOLD")
        self.assertEqual(r.reasons, ["unchecked: us_stock, supplier_score"])


class PriceFloor(unittest.TestCase):
    def test_floor_clears_gate_and_one_cent_less_does_not(self):
        landed = D("20.00")
        floor = lc.price_floor(landed, A)
        self.assertIsNotNone(floor)
        at = lc.evaluate(row(sale_price=str(floor), doba_cost="14.50", doba_shipping="5.50"), A)
        below = lc.evaluate(row(sale_price=str(floor - D("0.01")), doba_cost="14.50", doba_shipping="5.50"), A)
        self.assertEqual(at.verdict, "PASS", at.reasons)
        self.assertEqual(below.verdict, "FAIL")

    def test_floor_is_none_when_percentages_swallow_the_price(self):
        # 2.9 card + 2.0 fx + 98 refunds = 102.9% of the price: no price can clear the gate.
        a = lc.Assumptions(refund_pct=D("98"))
        self.assertIsNone(lc.price_floor(D("10"), a))

    def test_floor_reported_on_the_result(self):
        r = lc.evaluate(row(), A)
        self.assertEqual(r.price_floor, lc.price_floor(D("40"), A))


class Loading(unittest.TestCase):
    def test_load_skips_blank_and_comment_rows(self):
        text = (
            "name,sale_price,doba_cost,doba_shipping\n"
            "# a comment row,,,\n"
            ",,,\n"
            "widget,50,10,5\n"
        )
        rows = lc.load_rows(io.StringIO(text))
        self.assertEqual([r["name"] for r in rows], ["widget"])

    def test_load_requires_columns(self):
        with self.assertRaises(ValueError):
            lc.load_rows(io.StringIO("name,sale_price\nwidget,50\n"))

    def test_sort_order_and_json_shape(self):
        results = [
            lc.evaluate(row(name="c", category_flag="supplement"), A),
            lc.evaluate(row(name="b", sale_price="20", doba_cost="8", doba_shipping="5"), A),
            lc.evaluate(row(name="a"), A),
            lc.evaluate(row(name="z", doba_cost=""), A),
            lc.evaluate(row(name="h", ship_days=""), A),
        ]
        ordered = [r.verdict for r in lc.sort_results(results)]
        self.assertEqual(ordered, ["PASS", "HOLD", "FAIL", "REJECT", "UNKNOWN"])
        data = lc.to_jsonable(results[2])
        self.assertEqual(data["net"], "38.60")
        self.assertEqual(data["verdict"], "PASS")

    def test_template_file_runs(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "candidates.csv")
        with open(path, newline="", encoding="utf-8-sig") as handle:
            rows = lc.load_rows(handle)
        self.assertGreaterEqual(len(rows), 3)
        verdicts = {lc.evaluate(r, A).verdict for r in rows}
        self.assertTrue(verdicts <= set(lc.ORDER))


if __name__ == "__main__":
    unittest.main()
