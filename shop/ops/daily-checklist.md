# Daily checklist (about 20 minutes plus posting)

## Morning

- [ ] Shopify: new orders since yesterday. Any flagged high risk? Hold those (`doba-order-sop.md`).
- [ ] Doba: did each new order reach Doba and get charged? Any payment declines?
- [ ] Doba: tracking back on yesterday's orders? Any out-of-stock or price-change alerts?
- [ ] Float: is the balance above the buffer?
- [ ] Support inbox: answer everything with the macros. Target reply time: [N] business hours.
- [ ] Shopify and processor: any dispute or chargeback notice? Open it today.

## Content

- [ ] Post today's calendar row (`../content/calendar-30-day.md`). Checked against the claims checklist. Labeled if AI.
- [ ] Reply to comments within the hour. Answer only from the claims log.
- [ ] Note any clip with a fast spike. Re-cut candidates for the weekly review.

## Evening (5 minutes)

- [ ] Write today's numbers in your KPI notes: orders, refunds, late fulfilments, clips posted.
- [ ] Check that the store loads and checkout works on your phone.
- [ ] Look at the AutoDS, Doba and EcomBos billing dates. Any trial ending in the next 48 hours?

## Stop and check if

- Two orders from the same device or address with different cards.
- A product's refund requests double in a week.
- Doba shows a price that makes the margin gate fail. Run `python economics/landed_cost.py` and pause the product if it fails.
