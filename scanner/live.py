#!/usr/bin/env python3
"""Write data/sleeve/live.json — new listings, policy, and news on holdings.

    python3 scanner/live.py

Runs in seconds and touches one small file, so it can go every quarter hour
without troubling anyone. Kept apart from the quarterly filings scan for the
same reason prices are: these move hourly and that moves seasonally.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ciel.http import Session                  # noqa: E402
from ciel.emit.build import write_json         # noqa: E402
from ciel.sources import live, marketdata      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "sleeve", "live.json")
BUDGET = 96 * 1024


def main():
    session = Session(os.path.join(ROOT, "scanner", ".cache"))

    listings = live.coming_to_market(session)
    print("coming to market: %d filings" % len(listings))

    rules = live.policy(session)
    print("policy: %d documents" % len(rules))

    holdings = marketdata.held_slugs(ROOT)
    for holding in holdings:
        holding.setdefault("name", holding["ticker"])
    news = live.news_for(session, holdings) if holdings else {}
    print("news: %d holdings covered" % len(news))

    payload = {
        "schema_version": "1.0.0",
        "asof": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "listings": listings[:40],
        "policy": rules,
        "news": news,
        "note": ("Reported, never scored. Nothing here feeds the research queue, which is "
                 "built from filings alone. New registrations are the one genuinely early "
                 "signal available for free: a company files an S-1 weeks before it trades. "
                 "Headlines are the weakest item here by a distance - a price absorbs news in "
                 "milliseconds, so anything you read has already been paid for. It is here to "
                 "explain a move, not to catch one."),
    }
    size, changed = write_json(OUT, payload, BUDGET)
    print("%s %d bytes%s" % (OUT, size, "" if changed else " (unchanged)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
