#!/usr/bin/env python3
"""Write data/sleeve/prices.json — exchange rates always, quotes if a key exists.

    python3 scanner/prices.py

Deliberately separate from run.py. Rates and quotes change daily while the
filings scan is quarterly, and coupling them would mean either a stale franc
rate or a needless hour of SEC traffic. This runs in seconds and touches one
small file.

Environment:
    PRICE_API_KEY    optional; without it only exchange rates are written
    PRICE_PROVIDER   finnhub (default) or alphavantage
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ciel.http import Session                      # noqa: E402
from ciel.emit.build import write_json             # noqa: E402
from ciel.sources import marketdata                # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "sleeve", "prices.json")
BUDGET = 64 * 1024


def main():
    session = Session(os.path.join(ROOT, "scanner", ".cache"))
    key = os.environ.get("PRICE_API_KEY", "").strip()
    provider = os.environ.get("PRICE_PROVIDER", "finnhub").strip() or "finnhub"

    fx = marketdata.fetch_fx(session)
    print("rates: %d currencies" % len(fx))
    if "USD" not in fx:
        # Not fatal, but worth shouting about: almost every holding is a US
        # listing, so without this rate the buy ticket cannot compute shares.
        print("WARNING: no USD/CHF rate — the buy ticket will refuse foreign orders")

    holdings = marketdata.held_slugs(ROOT)
    if not holdings:
        # Nothing bought yet. Price the top of the queue instead, so the shop
        # shows what a share costs before anything is committed to.
        latest = os.path.join(ROOT, "data", "sleeve", "latest.json")
        if os.path.exists(latest):
            with open(latest, "r", encoding="utf-8") as handle:
                rows = json.load(handle).get("companies", [])
            holdings = [{"slug": r["slug"], "ticker": r.get("ticker", ""), "currency": "USD"}
                        for r in rows[:marketdata.MAX_SYMBOLS] if r.get("ticker")]
            print("no holdings yet; pricing the top %d of the queue" % len(holdings))
    else:
        print("holdings: %s" % ", ".join(h["ticker"] for h in holdings))

    prices = marketdata.fetch_prices(session, holdings, key, provider)
    if key:
        print("prices: %d of %d symbols" % (len(prices), len(holdings)))
    else:
        print("prices: skipped, PRICE_API_KEY is not set")

    payload = {
        "schema_version": "1.0.0",
        "asof": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "provider": provider if key else None,
        "fx_source": "Frankfurter / ECB reference rates",
        "fx": fx,
        "prices": prices,
        "note": ("Exchange rates are ECB reference rates and need no key. Share prices "
                 "require an API key held as a repository secret and are absent without "
                 "one; the portfolio then reports cost and holdings but no value, because "
                 "a portfolio that invents its own valuation is worse than one that admits "
                 "it has none."),
    }
    size, changed = write_json(OUT, payload, BUDGET)
    print("%s %d bytes%s" % (OUT, size, "" if changed else " (unchanged)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
