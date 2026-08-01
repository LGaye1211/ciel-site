#!/usr/bin/env python3
"""Validate committed output before it is pushed.

Runs in CI after every scan. Exits non-zero on breach so a bad artefact never
reaches the branch the site serves from.
"""

import json
import os
import re
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


# The Anthropic key and the GitHub token are entered on the device and held in
# localStorage. Neither has any business in a committed file, and this repository
# is public - a key that reaches a commit is a key that has to be revoked, and
# git history keeps it reachable long after the file is deleted. So the build
# refuses rather than trusting anyone to notice.
SECRET_PATTERNS = [
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}")),
    ("GitHub fine-grained token", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("GitHub classic token", re.compile(r"gh[posru]_[A-Za-z0-9]{30,}")),
]

TEXT_SUFFIXES = (".html", ".js", ".json", ".py", ".yml", ".yaml", ".md",
                 ".swift", ".plist", ".txt")


def fail(message):
    print("FAIL: %s" % message)
    return 1


def check_secrets(text, label):
    errors = 0
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors += fail("%s appears to contain a live %s - revoke it now, then remove it"
                           % (label, name))
    return errors


def scan_tree(root):
    errors = 0
    if not os.path.isdir(root):
        return 0
    for base, _dirs, names in os.walk(root):
        for name in names:
            if not name.endswith(TEXT_SUFFIXES):
                continue
            path = os.path.join(base, name)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    body = handle.read()
            except OSError:
                continue
            errors += check_secrets(body, os.path.relpath(path, ROOT))
    return errors


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

    # A sell trigger the review screen cannot evaluate is the worst kind of bug
    # this tool can have: the position reports itself armed and the check is
    # quietly skipped. It stayed hidden because nothing tied the trigger metrics
    # to the fields latest.json actually publishes. This is that tie.
    #
    # `going_concern` is the deliberate exception. It is a hard disqualifier, so
    # a company that develops it leaves the universe rather than tripping a
    # trigger, and the UI says so on the position instead of pretending.
    ROW_ALIASES = {"revenue_growth_yoy": "revenue_growth", "dilution_yoy": "dilution"}
    UNCHECKABLE = {"going_concern"}

    row_fields = set(companies[0].keys()) if companies else set()
    trigger_metrics = set()
    for row in companies:
        path = os.path.join(DATA, row.get("detail", ""))
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            for trigger in json.load(handle).get("triggers", []):
                if trigger.get("metric"):
                    trigger_metrics.add(trigger["metric"])
    orphans = sorted(
        m for m in trigger_metrics
        if m not in UNCHECKABLE and ROW_ALIASES.get(m, m) not in row_fields
    )
    for metric in orphans:
        errors += fail("trigger metric %r is armed on positions but never published in "
                       "latest.json, so it can never fire" % metric)
    if not orphans:
        print("ok  every checkable trigger metric (%d) is published in latest.json"
              % len(trigger_metrics - UNCHECKABLE))

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
            raw = handle.read()
        text = raw.lower()
        # A `for/else` here would print "ok" unconditionally - the else clause of
        # a for loop runs whenever the loop is not broken out of, which it never
        # was. The check passed every run regardless of what the page said.
        hits = [word for word in BANNED if word in text]
        for word in hits:
            errors += fail("banned framing in sleeve.html: %r" % word)
        if not hits:
            print("ok  sleeve.html clear of forecast framing")
        errors += check_secrets(raw, "sleeve.html")

    for name in ("charter", "data", "ios", ".github"):
        errors += scan_tree(os.path.join(ROOT, name))

    print("\n%s" % ("PASS" if not errors else "%d problem(s)" % errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
