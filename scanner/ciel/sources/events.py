"""Corporate events, funding story and legal exposure, from the filing history.

All of this comes out of the submissions record already fetched for every
company, so it costs no additional requests. 8-K item codes are the official
material-event feed: a company is legally required to file one within four
business days of the events below, which makes it a better and faster source
than press coverage, not a worse one.

Item codes are from SEC Form 8-K, General Instruction B.1.
"""

import datetime
import re

# The subset worth surfacing. Codes not listed here are administrative.
ITEMS = {
    "1.01": ("Material agreement entered", "deal", "good"),
    "1.02": ("Material agreement terminated", "deal", "warn"),
    "1.03": ("Bankruptcy or receivership", "legal", "crit"),
    "2.01": ("Completed an acquisition or disposal", "deal", "blue"),
    "2.02": ("Results announced", "results", "blue"),
    "2.03": ("Took on a material obligation", "finance", "warn"),
    "2.04": ("Triggered an acceleration of an obligation", "finance", "crit"),
    "2.05": ("Committed to exit or dispose costs", "finance", "warn"),
    "2.06": ("Material impairment", "finance", "crit"),
    "3.01": ("Delisting notice or listing-rule failure", "listing", "crit"),
    "3.02": ("Unregistered sale of equity", "finance", "warn"),
    "3.03": ("Holder rights modified", "finance", "warn"),
    "4.01": ("Changed accountants", "audit", "warn"),
    "4.02": ("Previously issued statements should no longer be relied upon", "audit", "crit"),
    "5.01": ("Change in control", "governance", "warn"),
    "5.02": ("Director or officer departure or appointment", "people", "warn"),
    "5.03": ("Fiscal year or bylaws amended", "governance", "blue"),
    "5.07": ("Shareholder vote results", "governance", "blue"),
    "7.01": ("Regulation FD disclosure", "news", "blue"),
    "8.01": ("Other material event", "news", "blue"),
}

# Filing types that tell the funding and corporate story.
STORY_FORMS = {
    "S-1": ("Registration statement filed — the IPO prospectus", "listing"),
    "S-1/A": ("Registration statement amended", "listing"),
    "424B4": ("IPO priced and offered", "listing"),
    "424B3": ("Prospectus supplement filed", "finance"),
    "424B5": ("Follow-on offering", "finance"),
    "S-3": ("Shelf registration filed — capacity to raise later", "finance"),
    "S-8": ("Employee share plan registered", "people"),
    "D": ("Private placement (Form D)", "funding"),
    "D/A": ("Private placement amended", "funding"),
    "SC 13D": ("Activist or control stake disclosed", "governance"),
    "SC 13G": ("Passive 5%+ stake disclosed", "governance"),
    "DEF 14A": ("Proxy statement — pay, board, votes", "governance"),
    "25-NSE": ("Delisting notification", "listing"),
    "15-12B": ("Deregistration — ceasing to report", "listing"),
}

LEGAL_HINTS = re.compile(
    r"\b(litigation|lawsuit|complaint|settlement|subpoena|investigation|"
    r"securities class action|SEC enforcement|consent order|injunction)\b", re.I)


def _parse(date_str):
    try:
        return datetime.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return None


def build_timeline(company, months=24, limit=40):
    """Material events from 8-K item codes, newest first."""
    cutoff = datetime.date.today() - datetime.timedelta(days=int(months * 30.4))
    out = []
    for filing in company.recent_filings or []:
        if filing["form"] not in ("8-K", "8-K/A"):
            continue
        filed = _parse(filing["date"])
        if filed and filed < cutoff:
            continue
        codes = [c.strip() for c in (filing.get("items") or "").split(",") if c.strip()]
        described = [ITEMS[c] for c in codes if c in ITEMS]
        if not described:
            continue
        out.append({
            "date": filing["date"],
            "form": filing["form"],
            "codes": codes,
            "events": [{"label": d[0], "kind": d[1], "tone": d[2]} for d in described],
            "url": company.filing_url(filing["accession"]),
        })
        if len(out) >= limit:
            break
    return out


def build_story(company, limit=30):
    """The corporate and funding story: how it listed and how it has raised."""
    out = []
    for filing in company.recent_filings or []:
        entry = STORY_FORMS.get(filing["form"])
        if not entry:
            continue
        out.append({
            "date": filing["date"],
            "form": filing["form"],
            "label": entry[0],
            "kind": entry[1],
            "url": company.filing_url(filing["accession"]),
        })
        if len(out) >= limit:
            break
    out.sort(key=lambda r: r["date"])
    return out


def legal_flags(company, timeline):
    """Filings that point at litigation or regulatory exposure.

    8-K item 8.01 is where most litigation disclosures land, and 1.03 is
    bankruptcy. This identifies *where to read*, not what the outcome is - the
    tool cannot judge a case and does not try.
    """
    out = []
    for event in timeline:
        for described in event["events"]:
            if described["kind"] == "legal" or described["label"].startswith("Bankruptcy"):
                out.append({"date": event["date"], "label": described["label"],
                            "url": event["url"], "tone": described["tone"]})
    for filing in company.recent_filings or []:
        if filing["form"] in ("SC 13D",):
            out.append({"date": filing["date"],
                        "label": "Activist or control stake disclosed",
                        "url": company.filing_url(filing["accession"]), "tone": "warn"})
    return out[:12]


def quarterly_reviews(company, limit=8):
    """One row per reported quarter, with the filing it came from.

    This is the 'quarterly review' the dossier asks for at age 16-17: revenue,
    margin, debt, cash flow, quarter by quarter, each linked to its 10-Q.
    """
    revenue = company.series.get("revenue")
    if not revenue or not revenue.points:
        return []

    gross = (company.series.get("gross_profit") or None)
    gross_by = gross.by_calendar() if gross else {}
    op = company.series.get("operating_income")
    op_by = op.by_calendar() if op else {}
    ocf = company.series.get("operating_cash_flow")
    ocf_by = ocf.by_calendar() if ocf else {}
    cash = company.series.get("cash")
    cash_by = cash.by_calendar() if cash else {}

    by_cal = revenue.by_calendar()
    rows = []
    for point in revenue.points[-limit:]:
        cal = point.calendar
        if not cal:
            continue
        year, quarter = cal
        prior = by_cal.get((year - 1, quarter))
        g = gross_by.get(cal)
        row = {
            "period": point.label,
            "revenue": point.val,
            "growth": ((point.val - prior.val) / prior.val) if prior and prior.val else None,
            "gross_margin": (g.val / point.val) if g and point.val else None,
            "operating_income": op_by[cal].val if cal in op_by else None,
            "operating_cash_flow": ocf_by[cal].val if cal in ocf_by else None,
            "cash": cash_by.get((year, quarter)).val if cash_by.get((year, quarter)) else None,
            "accession": point.accession,
            "url": company.filing_url(point.accession),
        }
        rows.append(row)
    rows.reverse()
    return rows
