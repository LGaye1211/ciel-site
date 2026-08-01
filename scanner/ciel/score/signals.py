"""Signal registry.

Each signal is a pure function of (company, metrics) returning a raw value, a
0-100 scaled value, and the evidence for it. `engine.py` never imports anything
from here by name - it looks signals up by the id the rubric asks for, so
retuning the rubric is a config edit and adding a *kind* of signal is a function
here. That split is what makes the rubric swappable.

A signal returning None is absent, not zero. The difference matters: a company
we know nothing about must not score the same as one we know is bad. The
`coverage` dimension exists to make that explicit.
"""

from ..model import Evidence

REGISTRY = {}


def signal(signal_id):
    def wrap(fn):
        REGISTRY[signal_id] = fn
        return fn
    return wrap


def band(value, points):
    """Piecewise-linear map. `points` is [(input, output)] ascending."""
    if value is None:
        return None
    if value <= points[0][0]:
        return points[0][1]
    if value >= points[-1][0]:
        return points[-1][1]
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        if value <= x1:
            span = (x1 - x0) or 1.0
            return y0 + (y1 - y0) * (value - x0) / span
    return points[-1][1]


def pct(value):
    return "%.1f%%" % (value * 100.0)


def money(value):
    a = abs(value or 0)
    for unit, size in (("bn", 1e9), ("m", 1e6), ("k", 1e3)):
        if a >= size:
            return "%s$%.1f%s" % ("-" if (value or 0) < 0 else "", a / size, unit)
    return "%s$%.0f" % ("-" if (value or 0) < 0 else "", a)


def _src(company, series_name=None, metric=None):
    """Link to the filing a figure came from, when we can identify it."""
    accession = ""
    series = company.series.get(series_name) if series_name else None
    if series and series.points:
        accession = series.points[-1].accession
    return company.filing_url(accession), accession


# --- Business quality -------------------------------------------------------

@signal("revenue_growth")
def revenue_growth(company, m):
    value = m.get("revenue_growth_yoy")
    if value is None:
        return None, None, []
    url, accn = _src(company, "revenue")
    basis = m.get("revenue_growth_basis", "")
    ev = [Evidence(
        "Revenue %s %s year on year, %s (%s to %s)." % (
            "grew" if value >= 0 else "fell", pct(abs(value)), basis,
            money(m.get("revenue_latest", 0) / (1 + value) if value != -1 else 0),
            money(m.get("revenue_latest", 0)),
        ),
        url, accn, basis,
    )]
    return value, band(value, [(-0.25, 0), (0, 25), (0.15, 55), (0.35, 80), (0.75, 100)]), ev


@signal("growth_stability")
def growth_stability(company, m):
    stdev = m.get("growth_stdev")
    share = m.get("growth_positive_share")
    if stdev is None or share is None:
        return None, None, []
    url, accn = _src(company, "revenue")
    n = m.get("growth_observations", 0)
    consistency = band(stdev, [(0.05, 100), (0.15, 75), (0.35, 45), (0.8, 10)])
    positive = share * 100.0
    scaled = 0.6 * consistency + 0.4 * positive
    ev = [Evidence(
        "Across the last %d year-on-year comparisons, growth was positive in %s of them, "
        "with a standard deviation of %s." % (n, pct(share), pct(stdev)),
        url, accn,
    )]
    return stdev, scaled, ev


@signal("gross_margin")
def gross_margin(company, m):
    value = m.get("gross_margin")
    if value is None:
        return None, None, []
    url, accn = _src(company, "gross_profit")
    ev = [Evidence("Gross margin %s in the latest reported quarter." % pct(value), url, accn)]
    return value, band(value, [(0.0, 0), (0.2, 30), (0.4, 60), (0.6, 85), (0.8, 100)]), ev


@signal("margin_trend")
def margin_trend(company, m):
    value = m.get("gross_margin_trend")
    if value is None:
        return None, None, []
    url, accn = _src(company, "gross_profit")
    direction = "expanded" if value >= 0 else "compressed"
    ev = [Evidence(
        "Gross margin %s from %s to %s against the same quarter a year earlier." % (
            direction, pct(m.get("gross_margin_prior", 0)), pct(m.get("gross_margin", 0)),
        ), url, accn,
    )]
    return value, band(value, [(-0.10, 0), (-0.02, 35), (0.0, 50), (0.03, 80), (0.10, 100)]), ev


# --- Margin of safety (Graham ch. 20) --------------------------------------

@signal("runway_months")
def runway_months(company, m):
    value = m.get("runway_months")
    if value is None:
        return None, None, []
    url, accn = _src(company, "operating_cash_flow")
    if m.get("cash_flow_positive"):
        ev = [Evidence(
            "Operating cash flow is positive over the trailing four quarters (%s), so there is "
            "no burn to outlast." % money(m.get("ocf_ttm", 0)), url, accn)]
        return value, 100.0, ev
    ev = [Evidence(
        "Cash of %s against a trailing operating burn of %s a year - about %.0f months at the "
        "current rate." % (money(m.get("cash", 0)), money(abs(m.get("ocf_ttm", 0))), value),
        url, accn,
    )]
    return value, band(value, [(6, 0), (12, 25), (24, 60), (36, 85), (60, 100)]), ev


@signal("net_cash_ratio")
def net_cash_ratio(company, m):
    value = m.get("net_cash_ratio")
    if value is None:
        return None, None, []
    url, accn = _src(company, "assets")
    net = m.get("net_cash", 0)
    ev = [Evidence(
        "%s %s against total assets of %s." % (
            "Net cash of" if net >= 0 else "Net debt of", money(abs(net)), money(m.get("assets", 0))),
        url, accn,
    )]
    return value, band(value, [(-0.4, 0), (-0.1, 30), (0.0, 50), (0.2, 80), (0.5, 100)]), ev


@signal("debt_to_equity")
def debt_to_equity(company, m):
    value = m.get("debt_to_equity")
    if value is None:
        if m.get("negative_equity"):
            url, accn = _src(company, "equity")
            return 99.0, 0.0, [Evidence(
                "Shareholders' equity is negative (%s)." % money(m.get("equity", 0)), url, accn)]
        return None, None, []
    url, accn = _src(company, "equity")
    ev = [Evidence(
        "Debt of %s against equity of %s - a ratio of %.2f." % (
            money(m.get("debt", 0)), money(m.get("equity", 0)), value), url, accn)]
    return value, band(value, [(0.0, 100), (0.3, 80), (0.8, 50), (1.5, 25), (3.0, 0)]), ev


@signal("dilution_rate")
def dilution_rate(company, m):
    value = m.get("dilution_yoy")
    if value is None:
        return None, None, []
    url, accn = _src(company, "diluted_shares")
    ev = [Evidence(
        "Diluted share count %s %s over the year (%s). Every share issued is a slice of your "
        "holding transferred to someone else." % (
            "rose" if value >= 0 else "fell", pct(abs(value)), m.get("dilution_basis", "")),
        url, accn,
    )]
    return value, band(value, [(-0.05, 100), (0.0, 90), (0.05, 65), (0.12, 30), (0.25, 0)]), ev


@signal("cash_self_sufficiency")
def cash_self_sufficiency(company, m):
    ocf = m.get("ocf_ttm")
    if ocf is None:
        return None, None, []
    url, accn = _src(company, "operating_cash_flow")
    positive = ocf > 0
    ev = [Evidence(
        "Trailing twelve-month operating cash flow of %s - the business %s fund itself." % (
            money(ocf), "does" if positive else "does not"), url, accn)]
    return ocf, (100.0 if positive else 0.0), ev


# --- Explainability (charter rule 7) ---------------------------------------

@signal("single_segment")
def single_segment(company, m):
    count = m.get("segment_count")
    if count is None:
        return None, None, []
    url, accn = _src(company)
    ev = [Evidence("%d reportable segment%s in the latest annual filing." % (
        count, "" if count == 1 else "s"), url, accn)]
    return count, band(count, [(1, 100), (2, 80), (4, 45), (8, 10)]), ev


@signal("description_clarity")
def description_clarity(company, m):
    text = (getattr(company, "description", "") or "").strip()
    sic = company.sic_description or ""
    if not text and not sic:
        return None, None, []
    words = len(text.split()) if text else 0
    url, accn = _src(company)
    if not words:
        return 0.0, 45.0, [Evidence(
            "No business description filed; classified by SIC as \"%s\"." % sic, url, accn)]
    scaled = band(words, [(5, 55), (25, 90), (60, 70), (150, 40)])
    return float(words), scaled, [Evidence(
        "Filed business description runs %d words: \"%s\"" % (
            words, text[:180] + ("..." if len(text) > 180 else "")), url, accn)]


@signal("balance_sheet_simplicity")
def balance_sheet_simplicity(company, m):
    assets = m.get("assets")
    if not assets:
        return None, None, []
    tangible = (m.get("cash") or 0)
    ratio = tangible / assets if assets else 0
    url, accn = _src(company, "assets")
    ev = [Evidence(
        "Cash and short-term investments are %s of total assets." % pct(ratio), url, accn)]
    return ratio, band(ratio, [(0.0, 40), (0.2, 65), (0.5, 90), (0.8, 100)]), ev


# --- Coverage ---------------------------------------------------------------

@signal("field_completeness")
def field_completeness(company, m):
    value = m.get("field_completeness")
    if value is None:
        return None, None, []
    return value, value * 100.0, [Evidence(
        "%d of 10 core financial fields are present in the XBRL data." % round(value * 10),
        company.filing_url(""),
    )]


@signal("history_depth")
def history_depth(company, m):
    value = m.get("quarters_reported")
    if value is None:
        return None, None, []
    return float(value), band(value, [(2, 10), (6, 45), (12, 80), (20, 100)]), [Evidence(
        "%d quarters of reported revenue available." % value, company.filing_url(""))]


# --- Team -------------------------------------------------------------------
# Populated by the team engine. Absent until then, which the coverage dimension
# already accounts for - these return None rather than zero on purpose.

@signal("insider_ownership")
def insider_ownership(company, m):
    value = m.get("insider_ownership")
    if value is None:
        return None, None, []
    return value, band(value, [(0.0, 10), (0.05, 45), (0.15, 80), (0.35, 100)]), [Evidence(
        "Officers and directors hold %s of shares outstanding." % pct(value),
        m.get("insider_ownership_url", company.filing_url("")))]


@signal("insider_selling")
def insider_selling(company, m):
    value = m.get("insider_selling")
    if value is None:
        return None, None, []
    return value, band(value, [(0.0, 100), (0.05, 70), (0.15, 35), (0.30, 0)]), [Evidence(
        "Insiders disposed of %s of their combined holdings over the last four quarters."
        % pct(value), m.get("insider_selling_url", company.filing_url("")))]


@signal("team_evidence")
def team_evidence(company, m):
    """How much we actually know about the team.

    Without this, a company with one usable ownership signal redistributes the
    whole dimension onto it and scores maximum on the thing the charter cares
    most about - which is exactly backwards. Same principle as the coverage
    dimension, applied within team.
    """
    filings = m.get("insider_filings_read")
    if filings is None:
        return None, None, []
    insiders = m.get("insider_count") or 0
    known = sum(1 for key in ("insider_ownership", "insider_selling") if m.get(key) is not None)
    scaled = band(filings, [(0, 0), (3, 35), (8, 70), (14, 100)]) * (0.5 + 0.25 * known)
    note = ""
    if m.get("insider_ownership_unreliable"):
        note = (" Reported holdings come to %.0f%% of the diluted share count, which points to a "
                "share class the diluted figure does not cover, so ownership is not scored here."
                % (m["insider_ownership_unreliable"] * 100))
    return float(filings), min(100.0, scaled), [Evidence(
        "%d ownership filing%s read, naming %d insider%s.%s" % (
            filings, "" if filings == 1 else "s", insiders, "" if insiders == 1 else "s", note),
        company.filing_url(""))]


@signal("prior_venture_count")
def prior_venture_count(company, m):
    value = m.get("prior_venture_count")
    if value is None:
        return None, None, []
    return float(value), band(value, [(0, 20), (1, 55), (2, 80), (4, 100)]), [
        Evidence(e["text"], e.get("source_url", "")) for e in m.get("prior_venture_evidence", [])
    ] or [Evidence("%d prior venture(s) identified among named officers." % value,
                   company.filing_url(""))]


@signal("prior_ipo_link")
def prior_ipo_link(company, m):
    value = m.get("prior_ipo_link")
    if value is None:
        return None, None, []
    return float(value), band(value, [(0, 0), (1, 100)]), [
        Evidence(e["text"], e.get("source_url", "")) for e in m.get("prior_ipo_evidence", [])
    ] or [Evidence("An officer was previously named on a company that later listed.",
                   company.filing_url(""))]
