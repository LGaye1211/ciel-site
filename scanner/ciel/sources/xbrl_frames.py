"""XBRL frames - the screening spine.

One request returns a concept for every filer in a period. This is how the whole
market gets screened in ~30 requests instead of tens of thousands: seed the
universe from frames, then pull full companyfacts only for survivors.
"""

FRAMES = "https://data.sec.gov/api/xbrl/frames/us-gaap/%s/USD/%s.json"

# Instant (balance sheet) concepts take a trailing "I" on the frame key;
# duration (income/cash flow) concepts do not.
INSTANT = {"Assets", "StockholdersEquity", "CashAndCashEquivalentsAtCarryingValue",
           "Liabilities", "LiabilitiesCurrent", "AssetsCurrent"}

# Filers disagree about which revenue tag to use. Screening on "Revenues" alone
# silently loses most of the modern market, so the union is taken.
REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
]

SEED_CONCEPTS = ["Assets"] + REVENUE_CONCEPTS


def frame_key(concept, year, quarter):
    key = "CY%dQ%d" % (year, quarter)
    return key + "I" if concept in INSTANT else key


def fetch_frame(session, concept, year, quarter):
    """Return {cik: {"val":, "entityName":, "accn":, "end":}} for one concept."""
    url = FRAMES % (concept, frame_key(concept, year, quarter))
    payload = session.get_json(url, ttl=None, default=None)
    if not payload or "data" not in payload:
        return {}
    out = {}
    for row in payload["data"]:
        cik = str(row.get("cik", "")).zfill(10)
        if not cik or cik == "0000000000":
            continue
        out[cik] = {
            "val": row.get("val"),
            "entityName": row.get("entityName", ""),
            "accn": row.get("accn", ""),
            "end": row.get("end", ""),
            "loc": row.get("loc", ""),
        }
    return out


def seed_universe(session, quarters, log=None):
    """Build the candidate pool from recent frames.

    `quarters` is a list of (year, quarter) newest first. A company enters the
    pool if it appears in any revenue frame; Assets is collected alongside for
    the size filter. Companies reporting assets but never revenue are excluded
    here rather than later - a company with no revenue is not a business we can
    read an annual report about.
    """
    revenue = {}
    assets = {}
    names = {}
    locations = {}

    for (year, quarter) in quarters:
        for concept in SEED_CONCEPTS:
            frame = fetch_frame(session, concept, year, quarter)
            if log and frame:
                log("frames %s %dQ%d: %d filers" % (concept, year, quarter, len(frame)))
            for cik, row in frame.items():
                names.setdefault(cik, row["entityName"])
                if row.get("loc"):
                    locations.setdefault(cik, row["loc"])
                if concept == "Assets":
                    assets.setdefault(cik, row["val"])
                else:
                    # Keep the largest revenue reading across tags/quarters as a
                    # rough scale signal; exact series come from companyfacts.
                    prior = revenue.get(cik)
                    if prior is None or (row["val"] or 0) > prior:
                        revenue[cik] = row["val"] or 0

    pool = {}
    for cik, rev in revenue.items():
        pool[cik] = {
            "cik": cik,
            "name": names.get(cik, ""),
            "revenue_hint": rev,
            "assets_hint": assets.get(cik),
            "loc": locations.get(cik, ""),
        }
    return pool
