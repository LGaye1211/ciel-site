"""The auto-drafted case.

Deterministic template generation from XBRL figures - no language model, so the
scan is free, reproducible and testable offline, and it can never invent a
figure. Every sentence carries the accession it came from.

Expect clear evidence-linked prose, not essay-quality argument. For deciding
where to spend attention, that is the right trade.
"""

from ..model import Evidence
from .signals import money, pct


def _url(company, series_name):
    series = company.series.get(series_name)
    accession = series.points[-1].accession if series and series.points else ""
    return company.filing_url(accession), accession


def build_bull(company):
    """Reasons this could work, strongest first. May legitimately be short."""
    m = company.metrics
    out = []

    growth = m.get("revenue_growth_yoy")
    if growth is not None and growth > 0.10:
        url, accn = _url(company, "revenue")
        out.append(Evidence(
            "Revenue grew %s year on year (%s), reaching %s in the quarter." % (
                pct(growth), m.get("revenue_growth_basis", ""), money(m.get("revenue_latest", 0))),
            url, accn))

    share = m.get("growth_positive_share")
    if share is not None and share >= 0.75 and m.get("growth_observations", 0) >= 4:
        url, accn = _url(company, "revenue")
        out.append(Evidence(
            "Growth has been positive in %s of the last %d year-on-year comparisons, so this is "
            "a trend rather than one good quarter." % (
                pct(share), m.get("growth_observations", 0)), url, accn))

    margin = m.get("gross_margin")
    if margin is not None and margin > 0.45:
        url, accn = _url(company, "gross_profit")
        out.append(Evidence(
            "Gross margin of %s means most of each additional sale falls through to cover fixed "
            "costs." % pct(margin), url, accn))

    trend = m.get("gross_margin_trend")
    if trend is not None and trend > 0.02:
        url, accn = _url(company, "gross_profit")
        out.append(Evidence(
            "Gross margin expanded from %s to %s against the same quarter a year earlier - the "
            "company is keeping more of what it sells, not buying growth with discounts." % (
                pct(m.get("gross_margin_prior", 0)), pct(margin)), url, accn))

    if m.get("cash_flow_positive"):
        url, accn = _url(company, "operating_cash_flow")
        out.append(Evidence(
            "Operating cash flow is positive at %s over the trailing year, so the business funds "
            "itself and is not dependent on raising money." % money(m.get("ocf_ttm", 0)),
            url, accn))

    net_cash = m.get("net_cash")
    if net_cash is not None and net_cash > 0 and m.get("assets"):
        url, accn = _url(company, "assets")
        out.append(Evidence(
            "Net cash of %s against total assets of %s - no debt overhang forcing decisions." % (
                money(net_cash), money(m.get("assets", 0))), url, accn))

    dilution = m.get("dilution_yoy")
    if dilution is not None and dilution < 0.02:
        url, accn = _url(company, "diluted_shares")
        out.append(Evidence(
            "Share count is close to flat (%s over the year), so growth in the business accrues "
            "to existing holders rather than being diluted away." % pct(dilution), url, accn))

    for member in company.team:
        for prior in member.get("prior_companies", []):
            if prior.get("outcome") == "ipo":
                out.append(Evidence(
                    "%s, %s here, was previously an officer of %s, which later listed." % (
                        member.get("raw_name", ""), member.get("title_filed", "an officer"),
                        prior.get("name", "")),
                    prior.get("source_url", "")))
                break
    return out


def build_summary(company):
    """The three-sentence explanation charter rule 7 demands."""
    m = company.metrics
    what = company.sic_description or "an operating business"
    where = company.country or company.state
    listing = "Listed on %s" % ", ".join(company.exchanges) if company.exchanges else "SEC-reporting"

    one = "%s is %s%s, classified by the SEC under \"%s\"." % (
        company.name, "a " if not what[:1].isupper() else "", what.lower(),
        company.sic_description or "n/a")
    if where:
        one = one[:-1] + ", based in %s." % where

    revenue = m.get("revenue_ttm")
    growth = m.get("revenue_growth_yoy")
    if revenue:
        two = "It reported %s of revenue over the trailing four quarters" % money(revenue)
        if growth is not None:
            two += ", %s %s against the same quarter a year earlier" % (
                "up" if growth >= 0 else "down", pct(abs(growth)))
        margin = m.get("gross_margin")
        two += ", at a gross margin of %s." % pct(margin) if margin is not None else "."
    else:
        two = "It has not reported revenue in a form we can read."

    if m.get("cash_flow_positive"):
        three = "%s, it funds itself from operations (%s of operating cash flow over the year)." % (
            listing, money(m.get("ocf_ttm", 0)))
    elif m.get("runway_months") is not None:
        three = ("%s, it is still consuming cash, with roughly %.0f months of runway at the "
                 "current burn." % (listing, m.get("runway_months", 0)))
    else:
        three = "%s." % listing

    return {
        "sentences": [one, two, three],
        "generated": True,
        "note": "Assembled from filing metadata and XBRL figures. Not editorial judgement - "
                "and rule 7 asks whether *you* can explain it, so rewrite this in your own "
                "words before you rely on it.",
    }


def build(company):
    bull = build_bull(company)
    return {
        "summary": build_summary(company),
        "bull": [e.to_json() for e in bull],
        "bull_count": len(bull),
    }
