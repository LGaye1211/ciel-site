#!/usr/bin/env python3
"""Margin gate for the Doba + Shopify model (U.S. customers only).

One row per candidate product goes in. One verdict per row comes out.

    python landed_cost.py candidates.csv
    python landed_cost.py candidates.csv --json
    python landed_cost.py candidates.csv --refund-pct 20 --fx-pct 0

CSV columns
    required   name, sale_price, doba_cost, doba_shipping
    checks     us_stock (yes/no), ship_days, supplier_score, category_flag
    free text  notes

Verdicts
    PASS     money gate and every check pass
    HOLD     money gate passes but a check column is blank. Fill it before you trust the row.
    FAIL     money gate fails: net per order or gross margin is under the minimum
    REJECT   hard rule hit: regulated category, not U.S.-stocked, too slow, weak supplier
    UNKNOWN  a required money column is blank or not a number

Stdlib only. Python 3.9+.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional

CENT = Decimal("0.01")
HUNDRED = Decimal(100)
REQUIRED_COLUMNS = ("name", "sale_price", "doba_cost", "doba_shipping")
NO_FLAG = {"", "none", "no", "n/a", "na", "-"}
YES = {"y", "yes", "true", "t", "1"}
NO = {"n", "no", "false", "f", "0"}
ORDER = {"PASS": 0, "HOLD": 1, "FAIL": 2, "REJECT": 3, "UNKNOWN": 4}


@dataclass(frozen=True)
class Assumptions:
    # Shopify Payments online card rate on the U.S. pricing page.
    # FILL: your Swiss account's rate. Shopify admin > Settings > Payments > Manage.
    pay_pct: Decimal = Decimal("2.9")
    pay_fixed: Decimal = Decimal("0.30")
    # 2 if you use a non-Shopify gateway on the Basic plan, else 0.
    gateway_extra_pct: Decimal = Decimal("0")
    # Payout currency conversion. ASSUMPTION.
    # FILL: Shopify admin > Settings > Payments > Payouts, note the conversion fee.
    fx_pct: Decimal = Decimal("2.0")
    # Doba's card payment fee on the wholesale cost plus shipping. ASSUMPTION.
    # FILL: the fee line on a real Doba order confirmation.
    doba_card_pct: Decimal = Decimal("3.0")
    # Refund and loss allowance as a share of the sale price. You never see the product.
    refund_pct: Decimal = Decimal("15")
    min_net: Decimal = Decimal("8")
    min_margin_pct: Decimal = Decimal("40")
    max_ship_days: int = 7
    # FILL: the scale Doba's supplier score uses. 4.0 assumes a 0-5 scale.
    min_supplier_score: Decimal = Decimal("4.0")


@dataclass
class Result:
    name: str
    verdict: str
    reasons: List[str] = field(default_factory=list)
    sale_price: Optional[Decimal] = None
    product_cost: Optional[Decimal] = None
    net: Optional[Decimal] = None
    margin_pct: Optional[Decimal] = None
    price_floor: Optional[Decimal] = None


class BadField(ValueError):
    """A cell holds something the gate cannot read."""


def parse_money(raw: Optional[str], column: str) -> Optional[Decimal]:
    if raw is None:
        return None
    text = raw.strip().replace("$", "").replace(",", "")
    if text == "":
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise BadField(f"{column}: not a number ({raw!r})")
    if not value.is_finite() or value < 0:
        raise BadField(f"{column}: must be zero or more ({raw!r})")
    return value


def parse_flag(raw: Optional[str], column: str) -> Optional[bool]:
    text = (raw or "").strip().lower()
    if text == "":
        return None
    if text in YES:
        return True
    if text in NO:
        return False
    raise BadField(f"{column}: use yes or no ({raw!r})")


def parse_days(raw: Optional[str]) -> Optional[int]:
    text = (raw or "").strip()
    if text == "":
        return None
    try:
        days = int(text)
    except ValueError:
        raise BadField(f"ship_days: whole number needed ({raw!r})")
    if days < 0:
        raise BadField(f"ship_days: must be zero or more ({raw!r})")
    return days


def product_cost(doba_cost: Decimal, doba_shipping: Decimal) -> Decimal:
    return doba_cost + doba_shipping


def net_per_order(sale: Decimal, cost_plus_ship: Decimal, a: Assumptions) -> Decimal:
    doba_fee = cost_plus_ship * a.doba_card_pct / HUNDRED
    shop_fee = sale * a.pay_pct / HUNDRED + a.pay_fixed
    gateway = sale * a.gateway_extra_pct / HUNDRED
    fx = sale * a.fx_pct / HUNDRED
    refund = sale * a.refund_pct / HUNDRED
    return sale - cost_plus_ship - doba_fee - shop_fee - gateway - fx - refund


def gross_margin_pct(sale: Decimal, cost_plus_ship: Decimal) -> Decimal:
    return (sale - cost_plus_ship) / sale * HUNDRED


def price_floor(cost_plus_ship: Decimal, a: Assumptions) -> Optional[Decimal]:
    """Lowest sale price, rounded up to the cent, that clears both money gates."""
    share = (a.pay_pct + a.gateway_extra_pct + a.fx_pct + a.refund_pct) / HUNDRED
    margin = a.min_margin_pct / HUNDRED
    if share >= 1 or margin >= 1:
        return None
    doba_fee = cost_plus_ship * a.doba_card_pct / HUNDRED
    by_net = (a.min_net + a.pay_fixed + cost_plus_ship + doba_fee) / (1 - share)
    by_margin = cost_plus_ship / (1 - margin)
    return max(by_net, by_margin).quantize(CENT, rounding=ROUND_CEILING)


def evaluate(row: Dict[str, str], a: Assumptions) -> Result:
    name = (row.get("name") or "").strip() or "(unnamed)"
    try:
        sale = parse_money(row.get("sale_price"), "sale_price")
        cost = parse_money(row.get("doba_cost"), "doba_cost")
        ship = parse_money(row.get("doba_shipping"), "doba_shipping")
        stock = parse_flag(row.get("us_stock"), "us_stock")
        days = parse_days(row.get("ship_days"))
        score = parse_money(row.get("supplier_score"), "supplier_score")
    except BadField as err:
        return Result(name, "UNKNOWN", [str(err)])

    missing = [
        column
        for column, value in (("sale_price", sale), ("doba_cost", cost), ("doba_shipping", ship))
        if value is None
    ]
    if missing:
        return Result(name, "UNKNOWN", ["missing: " + ", ".join(missing)])
    if sale == 0:
        return Result(name, "UNKNOWN", ["sale_price: must be above zero"])

    landed = product_cost(cost, ship)
    net = net_per_order(sale, landed, a)
    margin = gross_margin_pct(sale, landed)
    floor = price_floor(landed, a)

    rejects: List[str] = []
    flag = (row.get("category_flag") or "").strip()
    if flag.lower() not in NO_FLAG:
        rejects.append(f"regulated or restricted category: {flag}")
    if stock is False:
        rejects.append("not U.S.-stocked")
    if days is not None and days > a.max_ship_days:
        rejects.append(f"ship days {days} over {a.max_ship_days}")
    if score is not None and score < a.min_supplier_score:
        rejects.append(f"supplier score {score} under {a.min_supplier_score}")

    fails: List[str] = []
    if net < a.min_net:
        fails.append(f"net {net.quantize(CENT, ROUND_HALF_UP)} under {a.min_net}")
    if margin < a.min_margin_pct:
        fails.append(f"gross margin {margin.quantize(Decimal('0.1'), ROUND_HALF_UP)}% under {a.min_margin_pct}%")

    unchecked = [
        column
        for column, value in (("us_stock", stock), ("ship_days", days), ("supplier_score", score))
        if value is None
    ]

    if rejects:
        verdict, reasons = "REJECT", rejects + fails
    elif fails:
        verdict, reasons = "FAIL", fails
    elif unchecked:
        verdict, reasons = "HOLD", ["unchecked: " + ", ".join(unchecked)]
    else:
        verdict, reasons = "PASS", []

    return Result(name, verdict, reasons, sale, landed, net, margin, floor)


def load_rows(handle: Iterable[str]) -> List[Dict[str, str]]:
    reader = csv.DictReader(handle)
    names = [n.strip() for n in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in names]
    if missing:
        raise ValueError("missing column(s): " + ", ".join(missing))
    reader.fieldnames = names
    rows: List[Dict[str, str]] = []
    for raw in reader:
        clean = {k.strip(): (v or "").strip() for k, v in raw.items() if k is not None}
        if not any(clean.values()):
            continue
        if clean.get("name", "").startswith("#"):
            continue
        rows.append(clean)
    return rows


def sort_results(results: List[Result]) -> List[Result]:
    def key(r: Result):
        net = r.net if r.net is not None else Decimal("-1E9")
        return (ORDER[r.verdict], -net, r.name.lower())

    return sorted(results, key=key)


def fmt(value: Optional[Decimal], places: str = "0.01") -> str:
    if value is None:
        return "-"
    return str(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def render_table(results: List[Result]) -> str:
    headers = ("verdict", "name", "sale", "cost+ship", "net", "margin%", "floor", "why")
    rows = [
        (
            r.verdict,
            r.name,
            fmt(r.sale_price),
            fmt(r.product_cost),
            fmt(r.net),
            fmt(r.margin_pct, "0.1"),
            fmt(r.price_floor),
            "; ".join(r.reasons),
        )
        for r in results
    ]
    widths = [max([len(h)] + [len(row[i]) for row in rows]) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    out = [line, "  ".join("-" * w for w in widths)]
    for row in rows:
        out.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    return "\n".join(out)


def to_jsonable(r: Result) -> dict:
    data: dict = {"name": r.name, "verdict": r.verdict, "reasons": r.reasons}
    for key in ("sale_price", "product_cost", "net", "margin_pct", "price_floor"):
        value = getattr(r, key)
        data[key] = None if value is None else str(value.quantize(CENT, ROUND_HALF_UP))
    return data


def decimal_arg(text: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}")
    if not value.is_finite():
        raise argparse.ArgumentTypeError(f"not a finite number: {text!r}")
    return value


def main(argv: Optional[List[str]] = None) -> int:
    d = Assumptions()
    p = argparse.ArgumentParser(description="Margin gate for the Doba + Shopify model.")
    p.add_argument("csv_path", help="candidates CSV")
    p.add_argument("--json", action="store_true", help="print JSON instead of a table")
    p.add_argument("--pay-pct", type=decimal_arg, default=d.pay_pct, help="Shopify card fee percent")
    p.add_argument("--pay-fixed", type=decimal_arg, default=d.pay_fixed, help="Shopify card fee per order, dollars")
    p.add_argument("--gateway-extra-pct", type=decimal_arg, default=d.gateway_extra_pct, help="extra percent for a non-Shopify gateway")
    p.add_argument("--fx-pct", type=decimal_arg, default=d.fx_pct, help="payout conversion percent")
    p.add_argument("--doba-card-pct", type=decimal_arg, default=d.doba_card_pct, help="Doba card fee percent on cost + shipping")
    p.add_argument("--refund-pct", type=decimal_arg, default=d.refund_pct, help="refund and loss allowance percent of sale price")
    p.add_argument("--min-net", type=decimal_arg, default=d.min_net, help="minimum net per order, dollars")
    p.add_argument("--min-margin-pct", type=decimal_arg, default=d.min_margin_pct, help="minimum gross margin percent")
    p.add_argument("--max-ship-days", type=int, default=d.max_ship_days, help="maximum supplier ship days")
    p.add_argument("--min-supplier-score", type=decimal_arg, default=d.min_supplier_score, help="minimum supplier score")
    args = p.parse_args(argv)

    a = Assumptions(
        pay_pct=args.pay_pct,
        pay_fixed=args.pay_fixed,
        gateway_extra_pct=args.gateway_extra_pct,
        fx_pct=args.fx_pct,
        doba_card_pct=args.doba_card_pct,
        refund_pct=args.refund_pct,
        min_net=args.min_net,
        min_margin_pct=args.min_margin_pct,
        max_ship_days=args.max_ship_days,
        min_supplier_score=args.min_supplier_score,
    )

    try:
        with open(args.csv_path, newline="", encoding="utf-8-sig") as handle:
            rows = load_rows(handle)
    except (OSError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    results = sort_results([evaluate(row, a) for row in rows])

    if args.json:
        print(json.dumps([to_jsonable(r) for r in results], indent=2))
        return 0

    print(render_table(results))
    print()
    print(
        f"assumptions: card {a.pay_pct}% + {a.pay_fixed}, gateway extra {a.gateway_extra_pct}%, "
        f"fx {a.fx_pct}%, doba card {a.doba_card_pct}%, refunds {a.refund_pct}%"
    )
    print(
        f"PASS needs: net >= {a.min_net}, gross margin >= {a.min_margin_pct}%, "
        f"U.S. stock, ship days <= {a.max_ship_days}, supplier score >= {a.min_supplier_score}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
