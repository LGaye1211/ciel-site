# Doba bridge

AutoDS finds products. Doba ships them. **They are not connected.** AutoDS's own comparison page does not list Doba as a supplier source or an integration, and says Doba "needs to be paired with other dropshipping tools that handle the rest of the workflow after sourcing." So each AutoDS find has to be matched by hand to a Doba listing. Products Doba cannot supply are dropped.

## What Doba is (from its own pages and reviews)

- U.S.-stocked catalog, about 1 million or more products across roughly 1,000 suppliers (Doba's figures; other pages say 450,000 U.S.-stocked or 1.5 million).
- Domestic delivery quoted at 2-7 days. A review puts typical delivery at 3-7 days.
- Plans: Limited $29.99 a month (1 store, 30 listings), Basic $59.99 (250 listings, advanced research tool), Standard $149.99. Order cost, shipping fee and card fee are billed per order on top.
- Tools: one-click import, price and inventory monitoring, an AI tool hub, and Doba Pilot, an AI agent for research, sourcing, listing and fulfilment. Doba's pricing page lists a free-credits promotion for Pilot (30 product searches, 6 market insight reports). // FILL: whether it is still on offer for your account.
- It does not describe automatic order placement in detail. // FILL: after your first test checkout, note whether orders reach Doba on their own or need your approval.

## For each of the 15 candidates

1. **Search Doba.** Use the AutoDS title, then the product type, then Doba Pilot ("find U.S.-stocked products similar to [TITLE]").
2. **Decide: same product, close substitute, or nothing.** A substitute is a different product. It needs its own demand check from the AutoDS playbook and its own fidelity test later.
3. **Record the match** in the table below. One block per candidate.
4. **Fill `economics/candidates.csv`** with the Doba numbers, not the AutoDS numbers.
5. **Run the gate.** `python economics/landed_cost.py economics/candidates.csv`.

### Match record (copy per candidate)

```
candidate:            [AutoDS title]
doba listing:         [title]            same / substitute / none
supplier:             [name]             Doba supplier score: [value]  // FILL: scale
ships from:           [state]            stock units: [n]
handling time:        [business days]    delivery estimate: [days]
doba cost:            $[ ]               doba shipping: $[ ]
return policy shown:  yes / no           resale certificate needed: yes / no
photos:               [n] angles, [px] wide   dimensions and material listed: yes / no
price seen twice, 24 hours apart:  $[ ] / $[ ]
trademark or brand in images:      yes / no
```

## Supplier rubric (pass or fail, all must pass)

| Check | Pass |
|---|---|
| Stock | U.S. warehouse, enough units for a week of sales |
| Handling time | 2 business days or less |
| Delivery | 7 days or less (the margin gate rejects slower) |
| Doba supplier score | at least 4.0 on a 0-5 scale. // FILL: Doba's real scale and the metrics behind it |
| Return policy | visible, and the return address is in the U.S. |
| Photos | at least 3 angles, at least 1000 px wide. You need them for the AI video fidelity test. |
| Specs | dimensions, material and use are written down. They feed the claims log. |
| Price stability | the same price when checked twice, 24 hours apart |
| Brand risk | no trademarked logo or branded product in the images |
| Category | not regulated: supplements, cosmetics, kids' products, battery or mains electronics, branded goods |

A product that passes the rubric and the margin gate goes into the shortlist of 3-5. Open a claims log for it (`content/claims-checklist.md`).

## Reviews to keep in mind

- One review rates Doba 2.8 out of 5 and cites quality issues and poor support. The Shopify listing shows 4.3 from 49 reviews, with payment setup the most visible complaint.
- Reviewers call Doba margins thin. The gate is strict for that reason.
- A reviewer notes the payment to Doba is due immediately, before you are paid. See `ops/doba-order-sop.md` for the float.
