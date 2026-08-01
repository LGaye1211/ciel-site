"""Exchange rates and, where a key allows it, share prices.

Two sources with deliberately different standing.

Rates come from Frankfurter, which wraps the ECB reference rates, needs no key
and has no quota. They are therefore always present, and the buy ticket depends
on that: without a CHF rate a foreign share cannot be converted into a share
count, and the whole paper-portfolio idea collapses at the first screen. Rates
being free is what keeps the tool usable with nothing configured at all.

Prices need a key. Every free quote source that does not need one has closed or
moved behind a bot challenge - Stooq now answers with a JavaScript proof of
work, and Yahoo's undocumented endpoints return 429 to datacentre addresses.
So prices are optional, fetched here in CI with a repository secret and
committed, which keeps the key off the phone and avoids CORS entirely. When no
key is set this module still runs and still writes rates; the portfolio then
reports cost and holdings and says plainly that it cannot report value.

Never guess a rate and never carry a stale price forward silently. A portfolio
that invents its own valuation is worse than one that admits it has none.
"""

import json
import os

FRANKFURTER = "https://api.frankfurter.dev/v1/latest?base=%s&symbols=CHF"
CURRENCIES = ("USD", "EUR", "GBP", "CAD", "ILS", "SEK", "DKK", "NOK", "AUD", "JPY")

# Chosen because it is the one free tier whose quota comfortably covers a
# four-company sleeve plus benchmarks, and which documents daily closes rather
# than only real-time quotes.
FINNHUB = "https://finnhub.io/api/v1/quote?symbol=%s&token=%s"
ALPHA = ("https://www.alphavantage.co/query?function=GLOBAL_QUOTE"
         "&symbol=%s&apikey=%s")

MAX_SYMBOLS = 60


def fetch_fx(session):
    """{currency: rate to CHF}. Missing entries are omitted, never defaulted."""
    rates = {"CHF": 1.0}
    for currency in CURRENCIES:
        try:
            raw = session.get(FRANKFURTER % currency, ttl=6 * 3600)
            value = json.loads(raw).get("rates", {}).get("CHF")
        except Exception:  # noqa: BLE001 - one bad rate must not lose the rest
            continue
        if isinstance(value, (int, float)) and value > 0:
            rates[currency] = round(float(value), 6)
    return rates


def _finnhub(session, ticker, key):
    raw = session.get(FINNHUB % (ticker, key), ttl=3600)
    data = json.loads(raw)
    # Finnhub answers an unknown symbol with zeroes rather than an error, which
    # would otherwise be published as a real price of nothing.
    close = data.get("c")
    if not isinstance(close, (int, float)) or close <= 0:
        return None
    return {"close": round(float(close), 4), "previous": data.get("pc")}


def _alpha(session, ticker, key):
    raw = session.get(ALPHA % (ticker, key), ttl=3600)
    quote = json.loads(raw).get("Global Quote") or {}
    try:
        close = float(quote.get("05. price"))
    except (TypeError, ValueError):
        return None
    if close <= 0:
        return None
    return {"close": round(close, 4), "date": quote.get("07. latest trading day")}


PROVIDERS = {"finnhub": _finnhub, "alphavantage": _alpha}


def fetch_prices(session, holdings, key, provider, log=print):
    """holdings: [{slug, ticker, currency}]. Returns {slug: {...}}.

    A symbol that fails is left out rather than defaulted, so the frontend can
    tell "no price for this one" from "price of zero".
    """
    out = {}
    if not key or provider not in PROVIDERS:
        return out
    fetch = PROVIDERS[provider]
    for holding in holdings[:MAX_SYMBOLS]:
        ticker = (holding.get("ticker") or "").strip()
        if not ticker:
            continue
        try:
            quote = fetch(session, ticker, key)
        except Exception as exc:  # noqa: BLE001 - a dead quote is not a dead run
            log("  price %s failed: %s" % (ticker, exc))
            continue
        if not quote:
            log("  price %s: no usable quote" % ticker)
            continue
        quote["ticker"] = ticker
        quote["currency"] = holding.get("currency") or "USD"
        quote.setdefault("date", "")
        out[holding["slug"]] = quote
    return out


def held_slugs(root):
    """Companies actually bought, read from the committed charter records.

    The phone writes these back through the Contents API, so CI can see what is
    held without anything else being wired up. When nothing has been bought the
    caller falls back to the published queue.
    """
    directory = os.path.join(root, "charter", "positions")
    if not os.path.isdir(directory):
        return []
    out = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(directory, name), "r", encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            continue
        if record.get("slug") and record.get("ticker"):
            out.append({"slug": record["slug"], "ticker": record["ticker"],
                        "currency": record.get("currency") or "USD"})
    return out
