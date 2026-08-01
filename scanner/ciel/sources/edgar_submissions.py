"""EDGAR submissions - filing history, listing age, identity.

This is what turns a CIK into "a company that listed recently". The first
10-K/20-F filing date is the practical proxy for when it became a public
reporting company.
"""

import datetime
import re

from ..model import Company

SUBMISSIONS = "https://data.sec.gov/submissions/CIK%s.json"
ANNUAL_FORMS = {"10-K", "10-K405", "20-F", "40-F"}
SHELL_CATEGORIES = {"shell", "blank check"}


def _parse_date(value):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def fetch_company(session, cik, fallback_name=""):
    """Return a Company, or None if the submission record is unusable."""
    cik10 = str(cik).zfill(10)
    payload = session.get_json(SUBMISSIONS % cik10, ttl=7 * 86400, default=None)
    if not payload:
        return None

    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    accns = recent.get("accessionNumber", []) or []

    annual_dates = [d for f, d in zip(forms, dates) if f in ANNUAL_FORMS]
    first_annual = min(annual_dates) if annual_dates else ""

    # `recent` holds the last 1000 filings only. When a company has older
    # submission pages, its true first annual filing is earlier than anything
    # here - treat it as an established filer rather than guessing.
    has_older = bool(payload.get("filings", {}).get("files"))

    # SEC returns null entries in these arrays for securities with no listed
    # exchange, so they cannot be joined without filtering first.
    def clean(values):
        return [str(v) for v in (values or []) if v]

    company = Company(
        cik=str(int(cik10)),
        name=payload.get("name") or fallback_name,
        tickers=clean(payload.get("tickers")),
        exchanges=clean(payload.get("exchanges")),
        sic=str(payload.get("sic") or ""),
        sic_description=payload.get("sicDescription") or "",
        state=payload.get("stateOfIncorporationDescription") or "",
        fiscal_year_end=payload.get("fiscalYearEnd") or "",
        first_annual="" if has_older else first_annual,
        first_filing=min(dates) if dates else "",
        last_filing=max(dates) if dates else "",
        forms=sorted(set(forms)),
        is_foreign_filer=any(f in ("20-F", "40-F") for f in forms),
    )
    company.slug = make_slug(company.name, company.cik)
    company.country = _country(payload)

    docs = recent.get("primaryDocument", []) or []
    items = recent.get("items", []) or []
    # 8-K item codes ride along in the submissions record, so the material-event
    # timeline costs no additional requests.
    while len(items) < len(forms):
        items.append("")
    # Not truncated: ownership filings dominate by count (JFrog alone has 431
    # Form 4s), so slicing the head of this list drops the S-1 and the IPO
    # prospectus - exactly the filings the funding story is built from. Each
    # entry is a small dict and the list is capped at 1000 by EDGAR itself.
    company.recent_filings = [
        {"form": f, "date": d, "accession": a, "primary_document": p, "items": it}
        for f, d, a, p, it in zip(forms, dates, accns, docs, items)
    ]
    company.entity_category = (payload.get("category") or "").lower()
    company.description = payload.get("description") or ""
    company.website = payload.get("website") or ""
    company.has_older_filings = has_older
    return company


def _country(payload):
    addresses = payload.get("addresses") or {}
    business = addresses.get("business") or {}
    return business.get("stateOrCountryDescription") or ""


def years_since_listing(company, today=None):
    """Years since the first annual report. None when it cannot be established."""
    today = today or datetime.date.today()
    if company.has_older_filings:
        return 99.0
    first = _parse_date(company.first_annual)
    if not first:
        return None
    return (today - first).days / 365.25


def days_since_last_filing(company, today=None):
    today = today or datetime.date.today()
    last = _parse_date(company.last_filing)
    if not last:
        return None
    return (today - last).days


def looks_like_shell(company, universe):
    """Name and category heuristics for non-operating entities."""
    name = (company.name or "").lower()
    if company.entity_category and any(s in company.entity_category for s in SHELL_CATEGORIES):
        return True
    for pattern in universe.get("name_blocklist_patterns", []):
        if re.search(pattern, name):
            return True
    return False


def looks_leveraged(company, universe):
    name = (company.name or "").lower()
    return any(p in name for p in universe.get("leveraged_patterns", []))


def make_slug(name, cik):
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    base = re.sub(r"-(inc|corp|corporation|ltd|limited|plc|sa|ag|nv|llc|co|holdings|group)$", "", base)
    base = base[:48].strip("-") or "company"
    return "%s-%s" % (base, str(cik)[-6:])
