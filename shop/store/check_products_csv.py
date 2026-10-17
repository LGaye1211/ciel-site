#!/usr/bin/env python3
"""Check a Shopify product CSV before you upload it.

    python check_products_csv.py products.csv

Checks the classic Shopify product-import headers plus a few row rules.
Exit code 0 means no problems found, 1 means problems, 2 means the file could not be read.

// FILL: Shopify has been moving to newer column names (Title, URL handle, Description, ...).
// If the importer rejects this file, export one product from Shopify admin
// (Products > Export), copy its header row into products.csv, and adjust REQUIRED below.

Stdlib only. Python 3.9+.
"""

from __future__ import annotations

import csv
import re
import sys
from decimal import Decimal, InvalidOperation
from typing import Iterable, List

REQUIRED = [
    "Handle",
    "Title",
    "Body (HTML)",
    "Vendor",
    "Type",
    "Tags",
    "Published",
    "Option1 Name",
    "Option1 Value",
    "Variant SKU",
    "Variant Grams",
    "Variant Inventory Tracker",
    "Variant Inventory Policy",
    "Variant Fulfillment Service",
    "Variant Price",
    "Variant Requires Shipping",
    "Variant Taxable",
    "Image Src",
    "Image Position",
    "Image Alt Text",
    "Status",
]

HANDLE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
BOOLS = {"true", "false"}
STATUSES = {"active", "draft", "archived"}
POLICIES = {"deny", "continue"}


def check_rows(handle: Iterable[str]) -> List[str]:
    problems: List[str] = []
    reader = csv.DictReader(handle)
    headers = [h.strip() for h in (reader.fieldnames or [])]
    missing = [h for h in REQUIRED if h not in headers]
    if missing:
        problems.append("header: missing column(s): " + ", ".join(missing))
        return problems
    reader.fieldnames = headers

    seen = set()
    for number, raw in enumerate(reader, start=2):
        row = {k: (v or "").strip() for k, v in raw.items() if k is not None}
        if not any(row.values()):
            continue
        where = f"line {number}"
        handle_value = row["Handle"]
        if not handle_value:
            problems.append(f"{where}: Handle is empty")
            continue
        if not HANDLE.match(handle_value):
            problems.append(f"{where}: Handle {handle_value!r} must be lowercase letters, digits and hyphens")
        first = handle_value not in seen
        seen.add(handle_value)

        if first and not row["Title"]:
            problems.append(f"{where}: first row of {handle_value!r} needs a Title")
        if first and not row["Variant Price"]:
            problems.append(f"{where}: first row of {handle_value!r} needs a Variant Price")

        price_text = row["Variant Price"]
        if price_text:
            try:
                price = Decimal(price_text)
                if price < 0:
                    problems.append(f"{where}: Variant Price is negative")
                elif price == 0 and row["Status"].lower() == "active":
                    problems.append(f"{where}: active product with a zero price")
            except InvalidOperation:
                problems.append(f"{where}: Variant Price {price_text!r} is not a number")

        for column in ("Published", "Variant Requires Shipping", "Variant Taxable"):
            value = row[column]
            if value and value.lower() not in BOOLS:
                problems.append(f"{where}: {column} must be TRUE or FALSE, got {value!r}")
        if row["Status"] and row["Status"].lower() not in STATUSES:
            problems.append(f"{where}: Status must be active, draft or archived, got {row['Status']!r}")
        policy = row["Variant Inventory Policy"]
        if policy and policy.lower() not in POLICIES:
            problems.append(f"{where}: Variant Inventory Policy must be deny or continue, got {policy!r}")
        image = row["Image Src"]
        if image and not image.lower().startswith(("http://", "https://")):
            problems.append(f"{where}: Image Src must be a public http(s) URL")
        if "<script" in row["Body (HTML)"].lower():
            problems.append(f"{where}: Body (HTML) contains a script tag")
    return problems


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("usage: check_products_csv.py products.csv", file=sys.stderr)
        return 2
    try:
        with open(argv[1], newline="", encoding="utf-8-sig") as handle:
            problems = check_rows(handle)
    except OSError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    if problems:
        print("\n".join(problems))
        return 1
    print("ok: no problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
