# Doba order SOP and cash float

Doba bills you for each order when it is placed, before Shopify pays you. That gap is your **float**. If the float runs dry, orders stop.

## Flow (// FILL: confirm each step on your first real orders)

1. The customer pays in Shopify. Shopify holds the money until its payout.
2. The order reaches Doba. // FILL: automatically, or you approve it in the Doba app.
3. Doba charges your payment method for wholesale cost, shipping fee and card payment fee.
4. The supplier ships. Tracking comes back to Shopify through the Doba app. // FILL: how fast.
5. Shopify emails the customer the tracking.
6. Shopify pays out to your bank on its schedule. // FILL: the schedule for a new Swiss account, plus any holds or reserves.

## Before an order reaches Doba

If Doba waits for your approval, or while you watch the first orders, check each one in Shopify:

- [ ] Shopify's fraud analysis does not show high risk. If it does, hold. Contact the customer or cancel and refund.
- [ ] The address is real: street, city, state and ZIP agree. It is not a freight forwarder if your policy excludes them.
- [ ] The price on the order matches your price list. No price glitch.
- [ ] The product is still in stock at the supplier and the cost has not jumped.

Once Doba charges you, cancelling costs time and sometimes money.

## Float

```
float needed = Doba charges for all orders paid in the last [payout days] days
buffer       = 2 x average daily Doba charges, minimum $50
```

Starting float: $50-150 (see the plan's budget). Write `float_open` and `float_close` in `kpi-sheet.csv` every week. If the float falls under the buffer, slow the link-in-bio push until payouts catch up. Do not borrow against rent.

## Failure modes

| Failure | Sign | Action |
|---|---|---|
| Doba payment declined | order stuck | fix the payment method within the hour. If delay passes 24 hours, tell the customer. |
| Supplier out of stock after order | Doba status or email | offer a substitute, a wait with a new date, or a refund. Refund within one business day if there is no ship date. Mark the product unavailable in Shopify. |
| Supplier raised the cost | cost jumped | re-run `economics/landed_cost.py`, change the price or pause the product |
| Tracking missing after [X] days | no scan | contact Doba support with the order number, then tell the customer |
| Package late or lost | carrier exception | send the delay notice (`email/shipping-update.md`), reship or refund |
| Wrong or damaged item | customer report | follow `refund-chargeback-sop.md`. Ask for photos. |
| Duplicate order | two charges | cancel the duplicate in Doba immediately |
| Address error | returned to sender | contact the customer, decide who pays the reshipment |

## Records, per order

Shopify order number, Doba order number, Doba charge, tracking number, delivery date, issues. The KPI sheet sums them weekly.

## Reconcile weekly

Sum of Doba charges, sum of Shopify payouts and sum of refunds. The gap should equal float change plus fees. If not, find the missing order before next week.
