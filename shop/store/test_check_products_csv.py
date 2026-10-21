"""Tests for check_products_csv.py. Run from shop/store:  python -m unittest -v"""

import csv
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_products_csv as cp  # noqa: E402


def make(rows, headers=None):
    headers = headers or cp.REQUIRED
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        full = {h: "" for h in headers}
        full.update(r)
        writer.writerow(full)
    return io.StringIO(out.getvalue())


GOOD = {
    "Handle": "demo-product",
    "Title": "Demo",
    "Body (HTML)": "<p>Demo</p>",
    "Vendor": "[BRAND]",
    "Published": "FALSE",
    "Option1 Name": "Title",
    "Option1 Value": "Default Title",
    "Variant Inventory Policy": "deny",
    "Variant Fulfillment Service": "manual",
    "Variant Price": "29.99",
    "Variant Requires Shipping": "TRUE",
    "Variant Taxable": "TRUE",
    "Status": "draft",
}


class Checker(unittest.TestCase):
    def test_good_row_has_no_problems(self):
        self.assertEqual(cp.check_rows(make([GOOD])), [])

    def test_missing_header_reported(self):
        headers = [h for h in cp.REQUIRED if h != "Variant Price"]
        problems = cp.check_rows(make([GOOD], headers))
        self.assertEqual(len(problems), 1)
        self.assertIn("Variant Price", problems[0])

    def test_bad_handle(self):
        problems = cp.check_rows(make([dict(GOOD, Handle="Bad Handle")]))
        self.assertTrue(any("Handle" in p for p in problems))

    def test_price_must_be_a_number(self):
        problems = cp.check_rows(make([dict(GOOD, **{"Variant Price": "free"})]))
        self.assertTrue(any("not a number" in p for p in problems))

    def test_active_product_cannot_be_free(self):
        problems = cp.check_rows(make([dict(GOOD, **{"Variant Price": "0.00"}, Status="active")]))
        self.assertTrue(any("zero price" in p for p in problems))

    def test_draft_product_may_be_zero(self):
        self.assertEqual(cp.check_rows(make([dict(GOOD, **{"Variant Price": "0.00"})])), [])

    def test_first_row_needs_title(self):
        problems = cp.check_rows(make([dict(GOOD, Title="")]))
        self.assertTrue(any("Title" in p for p in problems))

    def test_extra_image_row_may_leave_title_blank(self):
        extra = {"Handle": "demo-product", "Image Src": "https://example.com/a.jpg", "Image Position": "2"}
        self.assertEqual(cp.check_rows(make([GOOD, extra])), [])

    def test_bad_booleans_and_status(self):
        row = dict(GOOD, Published="yes", Status="live")
        problems = cp.check_rows(make([row]))
        self.assertTrue(any("Published" in p for p in problems))
        self.assertTrue(any("Status" in p for p in problems))

    def test_image_must_be_http(self):
        problems = cp.check_rows(make([dict(GOOD, **{"Image Src": "C:/pic.jpg"})]))
        self.assertTrue(any("Image Src" in p for p in problems))

    def test_script_tag_flagged(self):
        problems = cp.check_rows(make([dict(GOOD, **{"Body (HTML)": "<script>x</script>"})]))
        self.assertTrue(any("script" in p for p in problems))

    def test_shipped_template_is_clean(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "products.csv")
        with open(path, newline="", encoding="utf-8-sig") as handle:
            self.assertEqual(cp.check_rows(handle), [])


if __name__ == "__main__":
    unittest.main()
