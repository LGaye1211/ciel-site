"""Assemble the committed JSON the frontend reads.

Only derived, pruned data is written here. Raw filings and API responses stay in
the gitignored cache - committing them would add tens of megabytes per run to a
repo that GitHub Pages has to serve.
"""

import json
import os

BUDGETS = {
    "manifest.json": 16 * 1024,
    "latest.json": 400 * 1024,
    "company": 30 * 1024,
}

COVERAGE_GAPS = [
    "US SEC filers only, plus foreign private issuers that file 20-F or 40-F. "
    "Swiss, EU and Asian listings that do not file with the SEC are absent - a real "
    "limitation for a CHF investor, and the honest reason is that free structured data "
    "for those markets does not exist at this quality.",
    "The data spine is American, which is precisely the bias the dossier warns about in "
    "section 3.3 when it says the United States is the best-performing market of the "
    "century and therefore the most biased sample.",
    "Figures come from XBRL as filed. Restatements are picked up on the next scan, not "
    "immediately.",
    "Officer information reflects the filing date, not today's team.",
    "Acquisitions are nearly invisible in SEC data, so any team track record here "
    "systematically understates success.",
    "Companies that never tag a discrete quarter (many fold Q4 into the annual report) "
    "show a sparser series. That is a reporting artefact, not a deterioration.",
]


def _round_floats(obj, places=3):
    if isinstance(obj, float):
        return round(obj, places)
    if isinstance(obj, dict):
        return {k: _round_floats(v, places) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(v, places) for v in obj]
    return obj


def write_json(path, payload, budget=None):
    """Write only when content changes, so a no-op run produces a clean diff."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(_round_floats(payload), separators=(",", ":"), sort_keys=False)
    size = len(text.encode("utf-8"))
    if budget and size > budget:
        raise ValueError("%s is %d bytes, over its %d byte budget" % (path, size, budget))
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            if handle.read() == text:
                return size, False
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return size, True


def spark(series, n=12):
    if not series or not series.points:
        return [], []
    points = series.points[-n:]
    return [round(p.val, 2) for p in points], [p.label for p in points]


def company_row(company, rank):
    m = company.metrics
    score = company.score
    revenue = company.series.get("revenue")
    values, labels = spark(revenue)
    top = [e["text"] for e in company.thesis.get("bull", [])[:3]]
    return {
        "id": "cik-%s" % company.cik10,
        "slug": company.slug,
        "name": company.name,
        "rank": rank,
        "score": round(score.total, 1) if score else 0,
        "dimensions": {k: round(v, 1) for k, v in (score.dimensions if score else {}).items()},
        "penalty_total": round(sum(p["points"] for p in score.penalties), 1) if score else 0,
        "ticker": company.primary_ticker,
        "exchanges": company.exchanges,
        "sector": company.sic_description,
        "country": company.country,
        "listed_years": round(company.listed_years, 1) if getattr(company, "listed_years", None) else None,
        "revenue_ttm": m.get("revenue_ttm"),
        "revenue_growth": m.get("revenue_growth_yoy"),
        "gross_margin": m.get("gross_margin"),
        "operating_margin": m.get("operating_margin"),
        "runway_months": (None if m.get("cash_flow_positive") else m.get("runway_months")),
        "cash_flow_positive": m.get("cash_flow_positive", False),
        "dilution": m.get("dilution_yoy"),
        "net_cash": m.get("net_cash"),
        "quarters": m.get("quarters_reported"),
        "annual_only": getattr(company, "annual_only", False),
        "spark_revenue": values,
        "spark_labels": labels,
        "top_reasons": top,
        "bear_count": len(company.thesis.get("bear", [])),
        "flags": [p["label"] for p in (score.penalties if score else [])],
        "detail": "companies/%s.json" % company.slug,
    }


MAX_TEAM = 20
MAX_CASE_ITEMS = 14


def company_dossier(company):
    """Trim to fit the byte budget rather than overrun it.

    A skipped dossier leaves latest.json referencing a file that is not there,
    which is a 404 when you tap the row. Dropping the least informative tail is
    strictly better than dropping the whole record.
    """
    m = company.metrics
    score = company.score
    series_out = {}
    for name in ("revenue", "gross_profit", "operating_income", "operating_cash_flow",
                 "diluted_shares", "cash", "equity", "assets"):
        series = company.series.get(name)
        if not series:
            continue
        values, labels = spark(series, 16)
        series_out[name] = {
            "concept": series.concept,
            "values": values,
            "labels": labels,
            "accessions": [p.accession for p in series.points[-16:]],
        }

    return {
        "schema_version": "1.0.0",
        "id": "cik-%s" % company.cik10,
        "cik": company.cik10,
        "slug": company.slug,
        "name": company.name,
        "ticker": company.primary_ticker,
        "exchanges": company.exchanges,
        "sector": company.sic_description,
        "sic": company.sic,
        "country": company.country,
        "website": getattr(company, "website", ""),
        "listed_years": round(company.listed_years, 1) if getattr(company, "listed_years", None) else None,
        "first_annual": company.first_annual,
        "last_filing": company.last_filing,
        "annual_only": getattr(company, "annual_only", False),
        "edgar_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=%s&type=10-K"
                     % company.cik10,
        "summary": company.thesis.get("summary", {}),
        "bull": company.thesis.get("bull", [])[:MAX_CASE_ITEMS],
        "bear": company.thesis.get("bear", [])[:MAX_CASE_ITEMS],
        "triggers": company.triggers,
        # Sorted by holding, so the tail dropped here is the least informative.
        "team": company.team[:MAX_TEAM],
        "team_truncated": max(0, len(company.team) - MAX_TEAM),
        "team_note": "Taken from Form 3/4/5 ownership filings over the last four quarters. These "
                     "are the people who filed, not necessarily the whole team - anyone who "
                     "neither holds nor trades shares does not appear. Holdings and sales are "
                     "counted only where a filing names a single insider, so joint filings are "
                     "excluded rather than split. There is no free structured source for "
                     "executive biographies, so prior-company history is not available here.",
        "metrics": {k: v for k, v in m.items() if not isinstance(v, (list, dict))},
        "series": series_out,
        "score": score.to_json() if score else {},
    }


def trim_dossier(dossier):
    """Drop the least informative content until the record fits its budget."""
    dossier["team"] = dossier.get("team", [])[:8]
    dossier["bull"] = dossier.get("bull", [])[:6]
    dossier["bear"] = dossier.get("bear", [])[:8]
    for name, series in list(dossier.get("series", {}).items()):
        series["values"] = series["values"][-8:]
        series["labels"] = series["labels"][-8:]
        series["accessions"] = series["accessions"][-8:]
    for contribution in dossier.get("score", {}).get("contributions", []):
        contribution["evidence"] = contribution.get("evidence", [])[:2]
    dossier["trimmed"] = True
    return dossier


def manifest(cohort, previous, counts, sources, rubric_version, generated_at, heartbeat,
             disqualification_counts):
    return {
        "schema_version": "1.0.0",
        "generated_at": generated_at,
        "heartbeat": heartbeat,
        "cohort": cohort,
        "previous_cohort": previous,
        "rubric_version": rubric_version,
        "counts": counts,
        "disqualifications": disqualification_counts,
        "sources": sources,
        "coverage_gaps": COVERAGE_GAPS,
        "disclaimer": "Research prioritisation, not investment advice. Scores rank what to "
                      "investigate; they are not forecasts of returns. This tool constitutes "
                      "neither investment advice nor a personalised recommendation within the "
                      "meaning of the Swiss Financial Services Act (FinSA/LSFin).",
    }
