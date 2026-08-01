"""Insider ownership and selling, from Form 3/4/5 XML.

This is the team dimension. There is no free structured source for executive
biographies, so what can be established honestly is: who the officers and
directors are, what they are called, how much of the company they hold, and
whether they have been selling.

That last one is the signal most commentary ignores and it is the one that is
hardest to argue with - a filing is a filing.

Transaction codes (SEC Form 345 spec): S is an open-market sale, P an
open-market purchase, A a grant or award, M an option exercise, F shares
withheld to cover tax, G a gift. Only S and P are discretionary; counting F as
"selling" would flag every executive whose vesting triggered withholding, which
is noise, not a decision.
"""

import re
import xml.etree.ElementTree as ET

ARCHIVE = "https://www.sec.gov/Archives/edgar/data/%d/%s/%s"
OWNERSHIP_FORMS = {"3", "4", "5"}
SELL_CODES = {"S"}
BUY_CODES = {"P"}


def _doc_url(cik, accession, primary_document):
    """The primaryDocument path carries an XSL renderer prefix that returns the
    rendered HTML. The machine-readable XML sits at the same path without it."""
    doc = re.sub(r"^xsl[^/]*/", "", primary_document or "")
    return ARCHIVE % (int(cik), accession.replace("-", ""), doc)


def _text(node, path):
    found = node.findtext(path)
    return found.strip() if found else ""


def _number(node, path):
    raw = _text(node, path)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def fetch_insiders(session, company, max_filings=12, since=""):
    """Aggregate recent ownership filings into per-person records.

    Returns (team, metrics). Both are empty when nothing could be read - absent
    rather than zero, so the scoring engine redistributes instead of punishing.
    """
    filings = [f for f in (company.recent_filings or [])
               if f["form"] in OWNERSHIP_FORMS and (not since or f["date"] >= since)]
    if not filings:
        return [], {}
    filings = filings[:max_filings]

    people = {}
    sold = bought = 0.0

    for filing in filings:
        if not filing.get("primary_document"):
            continue
        url = _doc_url(company.cik, filing["accession"], filing["primary_document"])
        try:
            raw = session.get(url, ttl=None)
        except Exception:  # noqa: BLE001 - a missing filing must not stop the scan
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            continue

        # Owners named in *this* document. Matching by filing date instead
        # cross-contaminates whenever several insiders file on the same day,
        # which is the norm after a vesting event.
        doc_owners = []

        for owner in root.findall(".//reportingOwner"):
            name = _text(owner, "reportingOwnerId/rptOwnerName")
            if not name:
                continue
            key = name.upper()
            doc_owners.append(key)
            rel = owner.find("reportingOwnerRelationship")
            is_officer = rel is not None and _text(rel, "isOfficer") in ("1", "true")
            is_director = rel is not None and _text(rel, "isDirector") in ("1", "true")
            title = (rel.findtext("officerTitle") or "").strip() if rel is not None else ""

            record = people.setdefault(key, {
                "raw_name": _tidy_name(name),
                "is_officer": False, "is_director": False,
                "title_filed": "", "shares": None, "last_filing": "",
                "sold": 0.0, "bought": 0.0, "shares_asof": "",
            })
            record["is_officer"] = record["is_officer"] or is_officer
            record["is_director"] = record["is_director"] or is_director
            if title and not record["title_filed"]:
                record["title_filed"] = title
            if filing["date"] > record["last_filing"]:
                record["last_filing"] = filing["date"]

        # Transactions sit outside reportingOwner in the schema, so they belong
        # to this document's owners. A Form 4 filed jointly by several people is
        # rare; when it happens the holding is genuinely ambiguous, so it is
        # left unset rather than duplicated across them.
        if not doc_owners:
            continue
        single = doc_owners[0] if len(doc_owners) == 1 else None

        for txn in root.findall(".//nonDerivativeTransaction"):
            code = _text(txn, "transactionCoding/transactionCode")
            shares = _number(txn, "transactionAmounts/transactionShares/value")
            after = _number(txn, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")
            if shares is None:
                continue
            # Counted only where the filer is unambiguous, so that the totals
            # and the per-person figures describe the same population. Taking
            # sales from joint filings while holdings come only from single
            # ones inflates the ratio - it was reporting 77% selling for a
            # company whose every listed insider showed no sales at all.
            if not single:
                continue
            if code in SELL_CODES:
                sold += shares
                people[single]["sold"] += shares
            elif code in BUY_CODES:
                bought += shares
                people[single]["bought"] += shares
            # Post-transaction holdings are per-filer, so only a single-owner
            # document can state one unambiguously. Take the most recent.
            if after is not None:
                if filing["date"] >= people[single].get("shares_asof", ""):
                    people[single]["shares"] = after
                    people[single]["shares_asof"] = filing["date"]

    if not people:
        return [], {}

    team = sorted(people.values(),
                  key=lambda p: (not p["is_officer"], -(p["shares"] or 0), p["raw_name"]))

    held = sum(p["shares"] or 0 for p in team)
    metrics = {}
    if held > 0:
        metrics["insider_shares"] = held
        diluted = company.metrics.get("shares_now")
        if diluted and diluted > 0:
            # Cap at 1: reported share counts and holdings come from different
            # filings and can disagree at the margin.
            metrics["insider_ownership"] = min(1.0, held / diluted)
            metrics["insider_ownership_url"] = company.filing_url(filings[0]["accession"])
    if sold + held > 0:
        metrics["insider_selling"] = sold / (sold + held)
        metrics["insider_selling_url"] = company.filing_url(filings[0]["accession"])
    metrics["insider_sold_shares"] = sold
    metrics["insider_bought_shares"] = bought
    metrics["insider_filings_read"] = len(filings)

    return [_public(p, company) for p in team], metrics


def _public(person, company):
    role = "Officer" if person["is_officer"] else ("Director" if person["is_director"] else "Insider")
    return {
        "raw_name": person["raw_name"],
        "role": role,
        "title_filed": person["title_filed"] or role,
        "shares": person["shares"],
        "sold_in_window": person["sold"],
        "bought_in_window": person["bought"],
        "last_filing": person["last_filing"],
        "source_url": company.filing_url(""),
        "confidence": "filed",
        "prior_companies": [],
    }


def _tidy_name(name):
    """EDGAR files names as "SURNAME FORENAME MIDDLE", shouted."""
    cleaned = re.sub(r"\s+", " ", name.replace(",", " ")).strip()
    if cleaned.isupper():
        parts = cleaned.split(" ")
        if len(parts) >= 2:
            parts = parts[1:] + [parts[0]]
        cleaned = " ".join(p.capitalize() for p in parts)
    return cleaned
