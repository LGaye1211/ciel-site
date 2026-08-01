# CIEL Learning Sleeve

A research terminal for the 10% learning sleeve in *Investing for the very long term*
(July 2026) — the part of the charter that says *two to four companies chosen and
followed personally, whose annual reports Arthur reads*.

**The app does the reading and the writing. You do the deciding.**

It finds young listed companies, pulls every quarterly filing, and arrives with the
case for, the case against, and quantified sell triggers already drafted. You set a
confidence level and accept. Reviews are pre-computed — there is nothing to type.

---

## What it is not

The dossier this is built from argues against stock selection: Sharpe's arithmetic,
Fama on public information already being in prices, Ellis on the loser's game. Those
citations are on the front page of the app and are not dismissible.

So this automates the *research and the discipline*, not the conviction. The number
next to each company is a **research priority score** — where to spend attention. It
is not a forecast of returns, and `verify.py` fails the build if forecast language
appears in the page.

---

## Running a scan

```bash
export SEC_USER_AGENT="Your Name your.email@example.com"   # SEC requires a contact
python3 scanner/run.py --mode deep
python3 scanner/verify.py
```

Python 3.11+, **standard library only**. There is no `requirements.txt`, and CI never
runs a dependency resolver.

| Flag | Effect |
|---|---|
| `--mode deep` | Full scan. ~10 min cold, ~100s on a warm cache. |
| `--mode light` | Current quarter only. Used by the weekly job. |
| `--mode dry` | Prints the ranking, writes nothing. |
| `--limit N` | Cap companies enriched. |
| `--no-team` | Skip Form 4 ownership — much faster while iterating on scoring. |
| `--offline` | Replay from cache, no network. |

Viewing the site locally needs a server — the page reads its data with `fetch()`,
which browsers block on `file://`:

```bash
python3 -m http.server 8000    # then open http://localhost:8000/sleeve.html
```

---

## How it decides

**It eliminates first and ranks second.** Ellis: between amateurs, points are lost
through unforced errors rather than won. Going-concern doubt, under twelve months of
runway, more than 25% annual dilution, stale or gapped data, shells and leveraged
instruments are hard cuts. The queue is headed by the elimination count and every
reason is shown.

What survives is scored against `scanner/config/rubric.json`:

| Dimension | Weight | |
|---|---|---|
| Team and history | 30 | Insider ownership and selling, from Form 3/4/5 |
| Business quality | 25 | Revenue growth, its consistency, gross margin and its direction |
| Margin of safety | 20 | Graham ch. 20 — runway, net cash, leverage, dilution |
| Can you explain it | 10 | Charter rule 7, made measurable |
| How much we know | 15 | Stops thin records ranking on the absence of bad news |

Two rules the engine enforces rather than leaving to convention: **a missing signal
redistributes its weight instead of scoring zero** (absent is not bad), and **every
contribution must carry evidence** with a link to the filing — `verify.py` fails the
build otherwise.

Retuning is a config edit. `engine.py` knows nothing about the rubric.

---

## Sell triggers

Generated per company, with thresholds derived from its *own* current figures, so a
52% margin floor means something different for a company at 61% than one at 22%.

Each is a machine-checkable predicate, not prose — which is the point. "If the story
changes" cannot be monitored; `gross_margin < 0.52 for 2 consecutive quarters` is
re-tested against every new filing by the weekly job. A fired trigger surfaces with
what you accepted, when, and what the number is now.

The tool never says what to do. It says what you said you would do.

---

## The charter, enforced

`charter/charter.json` holds the ten rules and how each is applied.

| Rule | How |
|---|---|
| 5 — sleeve ≤ 10%, never topped up | Four slots, hard. Accept disables at the cap. |
| 2 — view twice a year | Positions lock outside June and December. Research stays open all year — the objection is to watching your P&L, not to working. |
| 7 — explain in three sentences | Generated and shown before you can accept. |
| 9 — why, and what would make me sell | Auto-drafted and stored on accept; confidence required. |
| 10 — changes take 30 days | Pending changes sit visible and inert until they mature. |
| 6 — no leverage | Leveraged and inverse instruments never enter the universe. |

Accepting also computes the cost of the order — Swiss stamp duty 0.075%, foreign
0.15%, brokerage, FX spread — against §4.4's bar of 0.5% of the amount invested.

---

## Automation

| Workflow | When | What |
|---|---|---|
| `sleeve-quarterly.yml` | 8th of Jan/Apr/Jul/Oct | Deep scan, commits `data/sleeve/` |
| `sleeve-weekly.yml` | Mondays | Re-tests triggers, **always commits a heartbeat** |
| `ios-ipa.yml` | Manual or `ios-v*` tag | Unsigned `.ipa` on a macOS runner |

The weekly heartbeat is not decorative: GitHub disables scheduled workflows in public
repos after 60 days without a commit, and only a commit resets the timer. A quarterly
cron alone would be switched off before it fired a second time.

Secrets: `SEC_USER_AGENT` (required), `COMPANIES_HOUSE_KEY` (optional, UK).

---

## On the phone

`ios-ipa.yml` builds an unsigned `.ipa` and attaches it to a release. Install by
re-signing with Sideloadly or AltStore. A free Apple ID gives a 7-day certificate; a
paid developer account gives a year. That is iOS, not this build.

The app is a `WKWebView` pointed at the **live** site, so every scan reaches the phone
with no rebuild. Set your Pages URL in `ios/CielSleeve/Sources/ViewController.swift`.

To save decisions to the repository, add a fine-grained token in Settings, scoped to
**Contents: read and write on this repository only**. Every accept then becomes a
commit under `charter/positions/` — versioned, timestamped, and it survives a wiped
phone. It is a write credential on a phone: one repository is the whole blast radius,
and revoking it is one click if the device is lost.

---

## What it cannot see

Stated in the app's coverage panel too, from `manifest.json`, so it cannot drift.

- **SEC filers only**, plus foreign issuers filing 20-F/40-F. Swiss, EU and Asian
  listings that do not file with the SEC are absent — a real limitation for a CHF
  investor, and the honest reason is that free structured data for those markets does
  not exist at this quality.
- The spine is American, **which is exactly the bias §3.3 of the dossier warns about**
  when it says the United States is the best-performing market of the century and
  therefore the most biased sample.
- **No prior-company history for executives.** Form 3/4/5 gives who they are, what
  they hold and what they trade. Biographies would need a paid source.
- Ownership reflects who *files* — an officer holding no shares does not appear.
- It does not know whether any company is a good investment. It knows what was filed.

---

*Not investment advice, and not a personalised recommendation within the meaning of
the Swiss Financial Services Act (FinSA/LSFin). Past returns are no guide to future
returns, and any investment in equities carries a risk of capital loss.*
