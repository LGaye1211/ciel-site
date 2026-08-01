"""Per-company quarterly series from XBRL company facts.

This produces the four metrics the dossier names for age 16-17 - "read an annual
report: revenue, margin, debt, cash flow" - plus runway and dilution, which are
what actually kill a small holding and rarely appear in headline coverage.

Every figure keeps the accession it came from so the UI can link to the filing.
"""

import datetime
import re

from ..model import Point, Series

COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK%s.json"

# SEC normalises comparable periods into a `frame` key. Trusting it is far more
# reliable than inferring quarters from start/end dates ourselves, because it
# already resolves overlapping restatements and non-calendar fiscal years.
DURATION_FRAME = re.compile(r"^CY\d{4}Q\d$")
ANNUAL_FRAME = re.compile(r"^CY\d{4}$")
INSTANT_FRAME = re.compile(r"^CY\d{4}Q\dI$")

# Our metric name -> candidate us-gaap concepts, best first.
CONCEPTS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ],
    "cost_of_revenue": [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
        "CostOfServices",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "diluted_shares": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "short_term_investments": ["ShortTermInvestments", "MarketableSecuritiesCurrent"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "short_term_debt": ["LongTermDebtCurrent", "ShortTermBorrowings", "DebtCurrent"],
}

INSTANT_METRICS = {
    "cash", "short_term_investments", "assets", "liabilities", "equity",
    "long_term_debt", "short_term_debt",
}
# diluted_shares is a weighted average *over* a period, so it is a duration
# concept despite looking like a balance-sheet figure.


def fetch_facts(session, cik):
    return session.get_json(COMPANYFACTS % str(cik).zfill(10), ttl=3 * 86400, default=None)


def _extract(facts, concepts, instant):
    """Pull the first concept that yields usable normalised points."""
    gaap = (facts.get("facts") or {}).get("us-gaap") or {}
    dei = (facts.get("facts") or {}).get("dei") or {}
    for concept in concepts:
        node = gaap.get(concept) or dei.get(concept)
        if not node:
            continue
        for unit in ("USD", "shares", "USD/shares"):
            rows = (node.get("units") or {}).get(unit)
            if not rows:
                continue
            points = _normalise(rows, instant)
            if len(points) >= 2:
                return Series(concept=concept, unit=unit, points=points)
    return None


def _normalise(rows, instant):
    """Keep SEC-framed periods, newest filing wins on duplicates."""
    pattern = INSTANT_FRAME if instant else DURATION_FRAME
    chosen = {}
    for row in rows:
        frame = row.get("frame") or ""
        if not pattern.match(frame):
            continue
        prior = chosen.get(frame)
        if prior is None or (row.get("filed") or "") >= (prior.get("filed") or ""):
            chosen[frame] = row

    points = []
    for frame in sorted(chosen):
        row = chosen[frame]
        try:
            val = float(row.get("val"))
        except (TypeError, ValueError):
            continue
        points.append(Point(
            end=row.get("end", ""),
            start=row.get("start", ""),
            val=val,
            fy=int(row.get("fy") or 0),
            fp=row.get("fp") or "",
            form=row.get("form") or "",
            accession=row.get("accn") or "",
            frame=frame,
        ))
    return points


def _annual_fallback(facts, concepts):
    """20-F and 40-F filers report annually. Better a sparse series than none."""
    gaap = (facts.get("facts") or {}).get("us-gaap") or {}
    for concept in concepts:
        node = gaap.get(concept)
        if not node:
            continue
        rows = (node.get("units") or {}).get("USD") or (node.get("units") or {}).get("shares")
        if not rows:
            continue
        chosen = {}
        for row in rows:
            frame = row.get("frame") or ""
            if not ANNUAL_FRAME.match(frame):
                continue
            prior = chosen.get(frame)
            if prior is None or (row.get("filed") or "") >= (prior.get("filed") or ""):
                chosen[frame] = row
        if len(chosen) >= 2:
            points = []
            for frame in sorted(chosen):
                row = chosen[frame]
                try:
                    val = float(row.get("val"))
                except (TypeError, ValueError):
                    continue
                points.append(Point(
                    end=row.get("end", ""), start=row.get("start", ""), val=val,
                    fy=int(row.get("fy") or 0), fp="FY",
                    form=row.get("form") or "", accession=row.get("accn") or "",
                    frame=frame,
                ))
            return Series(concept=concept, unit="USD", points=points)
    return None


def entity_size(facts):
    """Public float and shares outstanding from the DEI cover-page tags.

    This is the only free valuation-adjacent figure in SEC data, and it is
    deliberately *not* scored. EntityPublicFloat is filed once a year on the
    10-K cover, stated as of the last business day of the prior second fiscal
    quarter, so it runs 12 months stale at best and several years at worst.
    Deriving a price-to-sales ratio from it would present an old number as a
    current valuation - the same error the stale_data disqualifier exists to
    prevent. It is carried as a size band, with its date shown.
    """
    dei = (facts.get("facts") or {}).get("dei") or {}
    out = {}

    node = dei.get("EntityPublicFloat")
    if node:
        rows = (node.get("units") or {}).get("USD") or []
        dated = [r for r in rows if r.get("end") and r.get("val")]
        if dated:
            latest = max(dated, key=lambda r: r["end"])
            out["public_float"] = float(latest["val"])
            out["public_float_asof"] = latest["end"]
            try:
                asof = datetime.date.fromisoformat(latest["end"])
                out["public_float_age_months"] = (
                    (datetime.date.today().year - asof.year) * 12
                    + (datetime.date.today().month - asof.month))
            except ValueError:
                pass

    node = dei.get("EntityCommonStockSharesOutstanding")
    if node:
        rows = (node.get("units") or {}).get("shares") or []
        dated = [r for r in rows if r.get("end") and r.get("val")]
        if dated:
            latest = max(dated, key=lambda r: r["end"])
            out["shares_outstanding"] = float(latest["val"])
            out["shares_outstanding_asof"] = latest["end"]
    return out


def build_series(facts):
    """Return {metric: Series} plus a flag for annual-only reporters."""
    series = {}
    annual_only = False
    for metric, concepts in CONCEPTS.items():
        found = _extract(facts, concepts, metric in INSTANT_METRICS)
        if found is None:
            found = _annual_fallback(facts, concepts)
            if found is not None and metric == "revenue":
                annual_only = True
        if found is not None:
            series[metric] = found
    return series, annual_only


def _last(series, metric, n=1):
    s = series.get(metric)
    if not s or not s.points:
        return None
    return s.points[-n] if len(s.points) >= n else None


def _val(series, metric, n=1):
    point = _last(series, metric, n)
    return point.val if point else None


def _gross_margin_at(series, when):
    """Gross margin for the latest quarter or the same quarter a year earlier.

    Both legs must come from the same period or the ratio is meaningless - which
    is exactly the bug positional indexing produces when a quarter is missing.
    """
    rev = series.get("revenue")
    if not rev or not rev.points:
        return None
    latest, prior = rev.year_ago()
    point = latest if when == "latest" else prior
    if point is None or not point.val:
        return None
    cal = point.calendar

    gross_series = series.get("gross_profit")
    if gross_series:
        match = gross_series.by_calendar().get(cal)
        if match is not None:
            return match.val / point.val

    cost_series = series.get("cost_of_revenue")
    if cost_series:
        match = cost_series.by_calendar().get(cal)
        if match is not None:
            return (point.val - match.val) / point.val
    return None


def derive_metrics(series):
    """Compute the derived figures the rubric and the writer both consume."""
    m = {}

    rev = series.get("revenue")
    if rev and rev.points:
        latest, year_ago = rev.year_ago()
        if year_ago and year_ago.val > 0:
            m["revenue_growth_yoy"] = (latest.val - year_ago.val) / year_ago.val
            m["revenue_growth_basis"] = "%s vs %s" % (latest.label, year_ago.label)

        m["revenue_latest"] = latest.val
        m["revenue_latest_label"] = latest.label
        m["revenue_ttm"] = sum(p.val for p in rev.points[-4:])
        m["quarters_reported"] = len(rev.points)

        # Growth history, matched on the calendar rather than by position, so a
        # missing quarter shifts nothing.
        by_cal = rev.by_calendar()
        growths = []
        for cal, point in sorted(by_cal.items()):
            year, quarter = cal
            base = by_cal.get((year - 1, quarter)) if quarter else by_cal.get((year - 1, 0))
            if base and base.val > 0:
                growths.append((point.val - base.val) / base.val)
        if len(growths) >= 3:
            recent = growths[-8:]
            mean = sum(recent) / len(recent)
            var = sum((g - mean) ** 2 for g in recent) / len(recent)
            m["growth_mean"] = mean
            m["growth_stdev"] = var ** 0.5
            m["growth_positive_share"] = sum(1 for g in recent if g > 0) / len(recent)
            m["growth_observations"] = len(recent)

    margin_now = _gross_margin_at(series, "latest")
    margin_then = _gross_margin_at(series, "year_ago")
    if margin_now is not None:
        m["gross_margin"] = margin_now
        if margin_then is not None:
            m["gross_margin_prior"] = margin_then
            m["gross_margin_trend"] = margin_now - margin_then

    revenue_now = _val(series, "revenue")
    op_series = series.get("operating_income")
    if op_series and op_series.points:
        op_latest, op_prior = op_series.year_ago()
        m["operating_income"] = op_latest.val
        if revenue_now:
            m["operating_margin"] = op_latest.val / revenue_now
        if op_prior is not None:
            m["operating_income_change"] = op_latest.val - op_prior.val

    ocf_series = series.get("operating_cash_flow")
    if ocf_series and ocf_series.points:
        recent = ocf_series.points[-4:]
        m["ocf_latest"] = recent[-1].val
        m["ocf_ttm"] = sum(p.val for p in recent)
        capex = series.get("capex")
        if capex and capex.points:
            m["fcf_ttm"] = m["ocf_ttm"] - sum(p.val for p in capex.points[-4:])

    cash = _val(series, "cash") or 0.0
    sti = _val(series, "short_term_investments") or 0.0
    debt = (_val(series, "long_term_debt") or 0.0) + (_val(series, "short_term_debt") or 0.0)
    m["cash"] = cash + sti
    m["debt"] = debt
    m["net_cash"] = (cash + sti) - debt

    assets = _val(series, "assets")
    equity = _val(series, "equity")
    if assets:
        m["assets"] = assets
        m["net_cash_ratio"] = m["net_cash"] / assets
    if equity is not None:
        m["equity"] = equity
        if equity > 0:
            m["debt_to_equity"] = debt / equity
        else:
            m["negative_equity"] = True

    burn = m.get("ocf_ttm")
    if burn is not None:
        if burn >= 0:
            m["runway_months"] = 999.0
            m["cash_flow_positive"] = True
        else:
            monthly = abs(burn) / 12.0
            m["runway_months"] = (m["cash"] / monthly) if monthly > 0 else 999.0
            m["cash_flow_positive"] = False

    shares = series.get("diluted_shares")
    if shares and shares.points:
        now, before = shares.year_ago()
        if before and before.val > 0:
            m["dilution_yoy"] = (now.val - before.val) / before.val
            m["dilution_basis"] = "%s vs %s" % (now.label, before.label)
            m["shares_now"] = now.val

    # How old the newest reported figure actually is. A company can be filing
    # on time while its XBRL series stops years earlier - usually because it
    # changed tags and SEC stopped assigning calendar frames to the new one.
    # Without this the tool will happily present four-year-old growth as
    # current, which is worse than showing nothing.
    if rev and rev.points:
        cal = rev.points[-1].calendar
        if cal:
            year, quarter = cal
            end_month = quarter * 3 if quarter else 12
            today = datetime.date.today()
            m["data_age_months"] = ((today.year - year) * 12 + (today.month - end_month))
            m["data_latest_period"] = rev.points[-1].label

        # Continuity: a gapped series is not the same as a short one, and a
        # growth rate computed across a hole is not a growth rate.
        cals = [p.calendar for p in rev.points if p.calendar]
        if len(cals) >= 2:
            span = (cals[-1][0] - cals[0][0]) * 4 + (cals[-1][1] - cals[0][1])
            m["series_density"] = len(cals) / float(span + 1) if span >= 0 else 1.0

    present = sum(1 for key in (
        "revenue_latest", "gross_margin", "operating_margin", "ocf_ttm",
        "cash", "debt", "assets", "equity", "dilution_yoy", "runway_months",
    ) if m.get(key) is not None)
    m["field_completeness"] = present / 10.0
    return m
