#!/usr/bin/env python3
"""Validate committed output before it is pushed.

Runs in CI after every scan. Exits non-zero on breach so a bad artefact never
reaches the branch the site serves from.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "sleeve")

BUDGETS = {"manifest.json": 16 * 1024, "latest.json": 400 * 1024}
DOSSIER_BUDGET = 30 * 1024

# The score is a research priority, not a forecast. These strings must never
# reach the page - a CI grep is the only thing that reliably keeps the framing
# honest as the copy evolves.
BANNED = ["skyrocket", "guaranteed", "will succeed", "buy signal",
          "predicted return", "sure thing", "can't lose"]


def fail(message):
    print("FAIL: %s" % message)
    return 1


def main():
    errors = 0

    for name, budget in BUDGETS.items():
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            errors += fail("%s is missing" % name)
            continue
        size = os.path.getsize(path)
        if size > budget:
            errors += fail("%s is %d bytes, over its %d budget" % (name, size, budget))
        else:
            print("ok  %-16s %6d bytes (budget %d)" % (name, size, budget))

    latest_path = os.path.join(DATA, "latest.json")
    if not os.path.exists(latest_path):
        return 1
    with open(latest_path, "r", encoding="utf-8") as handle:
        latest = json.load(handle)

    companies = latest.get("companies", [])
    if not companies:
        errors += fail("latest.json contains no companies")
    print("ok  %d companies published" % len(companies))

    seen = set()
    for row in companies:
        for key in ("id", "slug", "name", "rank", "score"):
            if key not in row:
                errors += fail("company row missing '%s': %s" % (key, row.get("name", "?")))
        if row["slug"] in seen:
            errors += fail("duplicate slug %s" % row["slug"])
        seen.add(row["slug"])

    # Every referenced dossier must exist, or the UI 404s on tap.
    missing = 0
    oversized = 0
    for row in companies:
        path = os.path.join(DATA, row.get("detail", ""))
        if not os.path.exists(path):
            missing += 1
            if missing <= 5:
                errors += fail("dossier referenced but absent: %s" % row.get("detail"))
        elif os.path.getsize(path) > DOSSIER_BUDGET:
            oversized += 1
            if oversized <= 5:
                errors += fail("dossier over budget: %s (%d bytes)"
                               % (row["detail"], os.path.getsize(path)))
    if not missing and not oversized:
        print("ok  every referenced dossier exists and is within budget")

    # Honesty contract: a scored claim with no evidence behind it is a bug.
    checked = bare = 0
    for row in companies[:40]:
        path = os.path.join(DATA, row.get("detail", ""))
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            dossier = json.load(handle)
        checked += 1
        for contribution in dossier.get("score", {}).get("contributions", []):
            if not contribution.get("evidence"):
                bare += 1
                if bare <= 5:
                    errors += fail("%s: signal '%s' scored with no evidence"
                                   % (row["slug"], contribution.get("signal_id")))
        if not dossier.get("bear"):
            errors += fail("%s: empty bear case - that is a generator bug, not a clean company"
                           % row["slug"])
    if checked and not bare:
        print("ok  %d dossiers checked, every contribution carries evidence" % checked)

    page = os.path.join(ROOT, "sleeve.html")
    if os.path.exists(page):
        with open(page, "r", encoding="utf-8") as handle:
            text = handle.read().lower()
        for word in BANNED:
            if word in text:
                errors += fail("banned framing in sleeve.html: %r" % word)
        else:
            print("ok  sleeve.html clear of forecast framing")

    print("\n%s" % ("PASS" if not errors else "%d problem(s)" % errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
