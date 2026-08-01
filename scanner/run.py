#!/usr/bin/env python3
"""CIEL learning-sleeve scanner.

    python3 scanner/run.py --mode deep
    python3 scanner/run.py --mode light --limit 200
    python3 scanner/run.py --offline          # replay from cache, no network

Stdlib only, by design: this must still run in 2029 without a dependency
resolver having opinions about it.
"""

import argparse
import datetime
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from ciel.cache import Cache, NullCache                      # noqa: E402
from ciel.emit import build as emit                          # noqa: E402
from ciel.http import Session                                # noqa: E402
from ciel.score import bearcase, disqualify, engine, thesis, triggers  # noqa: E402
from ciel.sources import edgar_submissions as subs           # noqa: E402
from ciel.sources import ownership, xbrl_facts, xbrl_frames  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data", "sleeve")
CONFIG_DIR = os.path.join(HERE, "config")

# Company facts run about a megabyte each, so an unbounded cache passes a
# gigabyte in one deep scan. actions/cache has to round-trip that on every CI
# run, which costs more time than the requests it saves.
CACHE_BUDGET_BYTES = 600 * 1024 * 1024


def load_config(name):
    with open(os.path.join(CONFIG_DIR, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


def log(message):
    print("[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), message), flush=True)


def recent_quarters(count, today=None):
    """Newest first. SEC frames lag, so start one quarter back."""
    today = today or datetime.date.today()
    year, quarter = today.year, (today.month - 1) // 3 + 1
    out = []
    for _ in range(count):
        quarter -= 1
        if quarter == 0:
            quarter = 4
            year -= 1
        out.append((year, quarter))
    return out


def cohort_label(today=None):
    today = today or datetime.date.today()
    quarter = (today.month - 1) // 3 + 1
    return "%dQ%d" % (today.year, quarter)


def previous_cohort(label):
    year, quarter = int(label[:4]), int(label[-1])
    quarter -= 1
    if quarter == 0:
        quarter, year = 4, year - 1
    return "%dQ%d" % (year, quarter)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("deep", "light", "dry"), default="deep")
    parser.add_argument("--limit", type=int, default=0, help="cap companies enriched")
    parser.add_argument("--offline", action="store_true", help="replay from cache only")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--check-budgets", action="store_true")
    parser.add_argument("--no-team", action="store_true",
                        help="skip Form 4 ownership (much faster iteration)")
    args = parser.parse_args()

    universe = load_config("universe.json")
    rubric = load_config("rubric.json")

    started = time.time()
    cache = NullCache() if args.no_cache else Cache(os.path.join(HERE, ".cache"))
    session = Session(cache=cache, offline=args.offline)

    quarters_back = 3 if args.mode == "light" else universe["frames_quarters_back"]
    quarters = recent_quarters(quarters_back)
    log("seeding universe from frames: %s" % ", ".join("%dQ%d" % q for q in quarters))
    pool = xbrl_frames.seed_universe(session, quarters, log=log)
    log("pool: %d filers reporting revenue" % len(pool))

    ceiling = universe["max_total_assets_usd"]
    candidates = [r for r in pool.values()
                  if not r.get("assets_hint") or r["assets_hint"] <= ceiling]
    # Newest CIK first. CIKs are issued in registration order, so this is a
    # strong recency prior and it costs nothing - scanning oldest-first spends
    # thousands of requests on companies that cannot pass the age filter.
    # Deliberately not sorted by revenue: that would bias the sample toward
    # mega-caps, the opposite of what this tool is looking for.
    candidates.sort(key=lambda row: row["cik"], reverse=True)
    log("after size ceiling: %d candidates" % len(candidates))

    today = datetime.date.today()
    # Insider activity over the trailing four quarters.
    ownership_since = (today - datetime.timedelta(days=400)).isoformat()
    cap = args.limit or universe["max_companies_to_enrich"]

    # Stage 1: listing age. One cached request each, and it is the filter that
    # actually defines the universe, so it runs before the expensive pull.
    young = []
    for row in candidates:
        try:
            company = subs.fetch_company(session, row["cik"], row.get("name", ""))
        except Exception as exc:  # noqa: BLE001
            log("submissions failed for %s: %s" % (row["cik"], exc))
            continue
        if company is None:
            continue
        years = subs.years_since_listing(company, today)
        if years is None or years > universe["max_years_since_first_annual"]:
            continue
        if company.sic in universe["sic_blocklist"]:
            continue
        company.listed_years = years
        company.is_shell = subs.looks_like_shell(company, universe)
        company.is_leveraged = subs.looks_leveraged(company, universe)
        days = subs.days_since_last_filing(company, today)
        company.stale = days is not None and days > universe["max_days_since_last_filing"]
        young.append(company)
        if len(young) >= cap:
            break

    log("listed within %d years: %d companies"
        % (universe["max_years_since_first_annual"], len(young)))

    survivors, disqualified, dq_counts, skipped = [], [], {}, []

    # Stage 2: financials, only for companies that passed the age filter.
    for examined, company in enumerate(young, 1):
        # Logged here rather than after scoring: a disqualified company skips
        # the rest of the loop, so a counter further down only reports when the
        # hundredth examined company happens to be a survivor.
        if examined % 50 == 0:
            log("  %d/%d examined - %d survive, %d eliminated"
                % (examined, len(young), len(survivors), len(disqualified)))
        try:
            facts = xbrl_facts.fetch_facts(session, company.cik)
        except Exception as exc:  # noqa: BLE001
            log("facts failed for %s: %s" % (company.name, exc))
            continue
        if not facts:
            continue

        company.series, company.annual_only = xbrl_facts.build_series(facts)
        company.metrics = xbrl_facts.derive_metrics(company.series)
        company.metrics.update(xbrl_facts.entity_size(facts))

        reasons = disqualify.check(company, rubric, universe)
        if reasons:
            company.disqualified = reasons
            for reason in reasons:
                dq_counts[reason["label"]] = dq_counts.get(reason["label"], 0) + 1
            disqualified.append(company)
            continue

        # Team: officers, holdings and selling from Form 3/4/5. There is no
        # free structured source for executive biographies, so this is what can
        # be established honestly - and insider selling is the signal most
        # commentary ignores.
        if not args.no_team:
            try:
                team, own = ownership.fetch_insiders(
                    session, company, max_filings=universe["ownership_filings_per_company"],
                    since=ownership_since)
                company.team = team
                company.metrics.update(own)
            except Exception as exc:  # noqa: BLE001
                log("ownership failed for %s: %s" % (company.name, exc))

        # One malformed record must not cost a ten-minute scan. Skip it, count
        # it, and let the run finish.
        try:
            engine.evaluate(company, rubric)
            company.thesis = thesis.build(company)
            company.thesis["bear"] = bearcase.build(company)
            company.triggers = triggers.build(company)
        except Exception as exc:  # noqa: BLE001
            log("scoring failed for %s (%s): %s" % (company.name, company.cik, exc))
            skipped.append((company.name, str(exc)))
            continue
        survivors.append(company)

    ordered = engine.rank(survivors)
    log("scored %d survivors, eliminated %d%s"
        % (len(ordered), len(disqualified),
           ", %d skipped on error" % len(skipped) if skipped else ""))

    if args.mode == "dry":
        for company in ordered[:15]:
            log("  %5.1f  %-42s %s" % (company.score.total, company.name[:42],
                                       company.primary_ticker))
        return 0

    cohort = cohort_label(today)
    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    publish_n = universe["publish_top_n"]
    dossier_n = universe["write_dossiers_top_n"]

    rows = [emit.company_row(c, i + 1) for i, c in enumerate(ordered[:publish_n])]
    latest = {
        "schema_version": "1.0.0",
        "cohort": cohort,
        "rubric_version": rubric.get("rubric_version", ""),
        "generated_at": generated_at,
        "companies": rows,
        "base_rates": rubric.get("base_rates", []),
        "eliminated": {
            "total": len(disqualified),
            "examined": len(ordered) + len(disqualified),
            "by_reason": dq_counts,
            "examples": [
                {"name": c.name, "ticker": c.primary_ticker,
                 "reasons": [r["detail"] for r in c.disqualified]}
                for c in disqualified[:60]
            ],
        },
    }
    size, changed = emit.write_json(os.path.join(DATA_DIR, "latest.json"), latest,
                                    emit.BUDGETS["latest.json"])
    log("latest.json %d bytes%s" % (size, "" if changed else " (unchanged)"))

    written = 0
    for company in ordered[:dossier_n]:
        path = os.path.join(DATA_DIR, "companies", "%s.json" % company.slug)
        dossier = emit.company_dossier(company)
        try:
            _, did = emit.write_json(path, dossier, emit.BUDGETS["company"])
        except ValueError:
            # Trim the evidence tail rather than skip the file: a missing
            # dossier is a 404 when the row is tapped.
            dossier = emit.trim_dossier(dossier)
            _, did = emit.write_json(path, dossier, emit.BUDGETS["company"])
            log("dossier trimmed to fit budget: %s" % company.slug)
        written += 1 if did else 0
    log("wrote %d dossiers (%d changed)" % (min(len(ordered), dossier_n), written))

    cohort_path = os.path.join(DATA_DIR, "quarters", "%s.json" % cohort)
    emit.write_json(cohort_path, {
        "cohort": cohort,
        "generated_at": generated_at,
        "rubric_version": rubric.get("rubric_version", ""),
        "ranking": [{"id": r["id"], "slug": r["slug"], "rank": r["rank"],
                     "score": r["score"], "dimensions": r["dimensions"]} for r in rows],
    })

    sources = [
        {"id": "xbrl_frames", "status": _status(session, "data.sec.gov"),
         "note": "Screening spine. SEC normalised calendar frames."},
        {"id": "xbrl_companyfacts", "status": _status(session, "data.sec.gov"),
         "note": "Per-company quarterly series."},
        {"id": "edgar_submissions", "status": _status(session, "data.sec.gov"),
         "note": "Filing history and listing age."},
        {"id": "companies_house", "status": "not_configured",
         "note": "UK officer histories. Needs COMPANIES_HOUSE_KEY."},
    ]
    counts = {
        "pool": len(pool),
        "examined": len(ordered) + len(disqualified),
        "eliminated": len(disqualified),
        "survived": len(ordered),
        "published": len(rows),
        "http_requests": session.stats["requests"],
        "cache_hits": session.stats["cache_hits"],
        "runtime_seconds": round(time.time() - started, 1),
    }
    emit.write_json(
        os.path.join(DATA_DIR, "manifest.json"),
        emit.manifest(cohort, previous_cohort(cohort), counts, sources,
                      rubric.get("rubric_version", ""), generated_at,
                      int(time.time()), dq_counts),
        emit.BUDGETS["manifest.json"])

    if hasattr(cache, "prune"):
        freed, kept = cache.prune(CACHE_BUDGET_BYTES)
        if freed:
            log("cache pruned: freed %.0fMB, kept %.0fMB" % (freed / 1e6, kept / 1e6))

    log("done in %.1fs - %d requests, %d cache hits"
        % (time.time() - started, session.stats["requests"], session.stats["cache_hits"]))
    return 0


def _status(session, host):
    return "degraded" if host in session.degraded else "ok"


if __name__ == "__main__":
    sys.exit(main())
