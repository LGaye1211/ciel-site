# Refund and chargeback SOP

You cannot inspect the product, so complaints are your only quality signal. Treat every one as data, and answer fast.

## Decision tree

1. **Customer writes about a problem.** Reply within [N] business hours with the macro in `support-macros.md`.
2. **Ask for what you need:** order number, a photo of the item and of the packaging, a description.
3. **Decide:**
   - Damaged, defective or wrong item: replace or refund. For orders under $[AMOUNT], refund without asking for a return.
   - Not as described: compare to the supplier listing and your claims log. If your page overstated, refund and fix the page.
   - Change of mind inside the return window: send return instructions, refund after the supplier or warehouse receives it. // FILL: match the supplier's return terms.
   - Late: follow the delay notice. Refund if they want to cancel.
4. **Refund in Shopify** the same day you decide. A refund costs less than a dispute.
5. **Log it:** order, product, supplier, reason, cost. Add it to the KPI sheet. Three issues of the same type on one product means pause it.

## Chargebacks (disputes)

A chargeback is a customer asking their bank to reverse a payment. It costs the order value plus a fee, and too many can freeze payouts. // FILL: the dispute fee and the dispute-rate limit in your payment provider's documentation.

1. **Prevent:** clear descriptor, fast support, honest delivery estimates, tracking on every order, a refund offered before the customer escalates.
2. **When one arrives:** open it the same day. Note the deadline. // FILL: the response window in your admin.
3. **Evidence packet** (collect from Shopify and Doba):
   - Order confirmation, customer name, email, IP address and billing address
   - Tracking number and carrier delivery confirmation with date and address
   - The product page and policies as they stood at the time of purchase (screenshots)
   - All emails with the customer
   - Proof the customer accepted the Terms and Returns policy at checkout
   - The supplier's shipping record from Doba
4. **Write the response in plain facts:** what was ordered, when it shipped, when it was delivered, what the customer said, what you offered. No arguing.
5. **If you cannot win:** accept it and refund. Do not fight a dispute you would lose.
6. **Fraud signs:** mismatched billing and shipping addresses, rush shipping demands, several orders from one device. Hold these before Doba charges you.

## Never

- Do not ignore a chargeback.
- Do not tell customers to cancel a dispute in exchange for a refund unless the processor allows it.
- Do not argue in the public review.
- Do not issue a refund in exchange for removing a review. That is review suppression.

## Prevention numbers to watch

Refund and complaint rate by product, disputes per 100 orders, late fulfilments per week. The plan's kill rules: pause a product past 8% refunds or complaints, pause a supplier after 3 late fulfilments in a week.
