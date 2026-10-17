# shop/ - Doba + AutoDS dropshipping kit

The model: **AutoDS finds products. Doba ships them from U.S. warehouses. Shopify sells them. Free AI-video tools and CapCut make the videos, with EcomBos as the paid upgrade.** U.S. customers only. You never touch the product.

> **This repo is public.** Everything under `shop/` is readable by anyone, and nothing here is merged to main. Files use placeholders only: `[BUSINESS NAME]`, `[ADDRESS]`, `[EMAIL]`. Real details go into Shopify and your own notes, never into these files.

## Run order (Day 0 = Sat 17 Oct 2026)

**Start with `START-HERE.md`.** It is the cheapest sequence: about $35-65 in fees by Day 40, plus a $50-100 order float.

| Step | File | Cost | Done when |
|---|---|---|---|
| 1 | `model/day0-gates.md` | about $1-30 | Doba and Shopify Payments each answered GO or NO-GO in writing |
| 2 | `model/video-stack.md` | $0 | transcript pasted to Claude (optional), differences fixed |
| 3 | `research/autods-playbook.md` | $0.99 trial | 15 candidates in `economics/candidates.csv` |
| 4 | `research/doba-bridge.md`, `economics/` | $0 | 3-5 products PASS the gate |
| 5 | `store/` | Shopify about $1, domain about $1 | store live, test checkout passed |
| 6 | `content/` | $0 with the free video route. EcomBos Pro $37-49 only after a trigger. | fidelity test passed, first video posted |
| 7 | `ops/` | $0 | daily and weekly routines running |
| 8 | `entity/` | $130-400 | only if you fund the LLC lane |

Kill rules and the budget are in `START-HERE.md`. Short version: total outlay capped at $250 until 10 real sales, pause any product past 8% refunds or complaints, stop and review at Day 40 (about 26 Nov) if there are no add-to-carts.

## Commands (Python 3.9+, standard library only)

```
cd shop/economics
python -m unittest                        # 28 tests
python landed_cost.py candidates.csv      # verdict per product
python landed_cost.py candidates.csv --json
python landed_cost.py candidates.csv --refund-pct 20 --fx-pct 0

cd ../store
python -m unittest                        # 12 tests
python check_products_csv.py products.csv
```

## Conventions

- `// FILL:` marks a value only your own dashboard settles. The exact step to get it follows.
- `[BRACKETS]` mark placeholders. Replace them inside Shopify, not in this repo.
- Anything marked **unverified** came from vendor blogs or a single source. Check it before relying on it.
- Policy pages, the LLC documents and tax notes are templates, not legal or tax advice. Have a professional review them before use.

## What Claude cannot do for you

Log into Shopify, AutoDS, Doba, EcomBos or a bank. Pay anything. Post videos. Form the LLC or file anything. Open the video in your browser. Give legal or tax advice. Everything else in this folder is prepared so you can do those steps quickly.

## Map

```
model/       what the video shows, Day 0 gates, gate results
research/    AutoDS playbook, Doba bridge
economics/   margin gate (landed_cost.py), tests, candidates.csv
store/       Shopify setup, AI store builder notes, pages, products.csv and its checker
brand/       names, voice, palette, logo prompts
content/     30-day calendar, hooks, scripts, EcomBos guide, claims checklist
email/       welcome, abandoned cart, shipping update, review request
entity/      U.S. LLC runbook, operating agreement template, Swiss sole proprietor steps, adviser questions, calendar
ops/         daily and weekly routines, Doba order SOP, refunds and chargebacks, support macros, KPI sheet
```
