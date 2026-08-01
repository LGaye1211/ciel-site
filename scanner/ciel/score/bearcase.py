"""The case against, argued as hard as the case for.

Rendered level with the bull case in the UI, never beneath it. If this comes
back empty for a company, that is a generator bug rather than a clean company -
test_thesis.py asserts it, because a research tool that only finds reasons to
buy is worse than no tool at all.
"""

from ..model import Evidence
from .signals import money, pct


def _url(company, series_name):
    series = company.series.get(series_name)
    accession = series.points[-1].accession if series and series.points else ""
    return company.filing_url(accession), accession


def build(company):
    m = company.metrics
    out = []

    growth = m.get("revenue_growth_yoy")
    if growth is not None and growth < 0.05:
        url, accn = _url(company, "revenue")
        out.append(Evidence(
            "Revenue %s %s year on year (%s). Whatever the story is, it is not currently "
            "showing up in sales." % (
                "fell" if growth < 0 else "grew only", pct(abs(growth)),
                m.get("revenue_growth_basis", "")), url, accn))

    stdev = m.get("growth_stdev")
    if stdev is not None and stdev > 0.30:
        url, accn = _url(company, "revenue")
        out.append(Evidence(
            "Growth is erratic - a standard deviation of %s across %d comparisons. Lumpy revenue "
            "usually means few customers or long contracts, and both make any single quarter a "
            "poor guide." % (pct(stdev), m.get("growth_observations", 0)), url, accn))

    trend = m.get("gross_margin_trend")
    if trend is not None and trend < -0.01:
        url, accn = _url(company, "gross_profit")
        out.append(Evidence(
            "Gross margin compressed from %s to %s against the same quarter a year earlier. "
            "Either input costs are rising or the company is discounting to hold volume." % (
                pct(m.get("gross_margin_prior", 0)), pct(m.get("gross_margin", 0))), url, accn))

    margin = m.get("gross_margin")
    if margin is not None and margin < 0.25:
        url, accn = _url(company, "gross_profit")
        out.append(Evidence(
            "Gross margin is only %s, so scale has to be enormous before anything reaches the "
            "bottom line." % pct(margin), url, accn))

    if m.get("operating_margin") is not None and m["operating_margin"] < 0:
        url, accn = _url(company, "operating_income")
        out.append(Evidence(
            "The company is loss-making at the operating line (%s margin). Profitability is a "
            "forecast, not a fact." % pct(m["operating_margin"]), url, accn))

    change = m.get("operating_income_change")
    if change is not None and change < 0 and (m.get("operating_income") or 0) < 0:
        url, accn = _url(company, "operating_income")
        out.append(Evidence(
            "The operating loss widened by %s against the same quarter a year earlier - it is "
            "getting worse, not better." % money(abs(change)), url, accn))

    runway = m.get("runway_months")
    if runway is not None and not m.get("cash_flow_positive") and runway < 36:
        url, accn = _url(company, "operating_cash_flow")
        out.append(Evidence(
            "About %.0f months of cash at the current burn (%s against %s a year). A company "
            "that must raise is a company that raises on the buyer's terms." % (
                runway, money(m.get("cash", 0)), money(abs(m.get("ocf_ttm", 0)))), url, accn))

    dilution = m.get("dilution_yoy")
    if dilution is not None and dilution > 0.05:
        url, accn = _url(company, "diluted_shares")
        out.append(Evidence(
            "Diluted share count rose %s over the year (%s). The company can grow while your "
            "share of it shrinks, and this is the number most commentary ignores." % (
                pct(dilution), m.get("dilution_basis", "")), url, accn))

    d2e = m.get("debt_to_equity")
    if d2e is not None and d2e > 1.0:
        url, accn = _url(company, "equity")
        out.append(Evidence(
            "Debt of %s against equity of %s. Leverage decides who controls the outcome if "
            "trading deteriorates, and it is not the shareholder." % (
                money(m.get("debt", 0)), money(m.get("equity", 0))), url, accn))

    if m.get("negative_equity"):
        url, accn = _url(company, "equity")
        out.append(Evidence(
            "Shareholders' equity is negative (%s) - liabilities exceed assets on the balance "
            "sheet." % money(m.get("equity", 0)), url, accn))

    quarters = m.get("quarters_reported") or 0
    if quarters < 8:
        out.append(Evidence(
            "Only %d quarters of reported history. There is no track record here to speak of, "
            "and a short series flatters whatever the recent trend happens to be." % quarters,
            company.filing_url("")))

    completeness = m.get("field_completeness")
    if completeness is not None and completeness < 0.7:
        out.append(Evidence(
            "Only %d of 10 core financial fields are present in the XBRL data, so parts of this "
            "assessment rest on absence rather than evidence." % round(completeness * 10),
            company.filing_url("")))

    if getattr(company, "annual_only", False):
        out.append(Evidence(
            "A foreign private issuer reporting annually rather than quarterly. Problems surface "
            "months later here than they would at a domestic filer.", company.filing_url("")))

    if not company.team:
        out.append(Evidence(
            "No officer history could be reconstructed from public filings, so the team - the "
            "thing that matters most - is the thing we know least about.",
            company.filing_url("")))

    # The base rate always applies, so it is always stated.
    out.append(Evidence(
        "Base rate: 57.8% of US common stocks underperformed one-month Treasury bills over their "
        "lifetimes (Bessembinder, Journal of Financial Economics, 2018). Nothing above changes "
        "that starting point.",
        "https://doi.org/10.1016/j.jfineco.2018.06.004"))

    return [e.to_json() for e in out]
