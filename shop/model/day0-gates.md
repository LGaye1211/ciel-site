# Day 0 gates

Two checks decide whether this model can run for you at all. Together they cost about $1-30. Do them before any other spending. Write each answer into `gate-results.md`.

Opening Shopify on Day 0 is fine. The U.S. pricing page shows a 3-day free trial, then $1/month for 3 months. // FILL: confirm the offer on your Swiss sign-up page.

## Gate A - does Doba accept you?

Every product ships through Doba, so this comes first.

What is known:
- Doba's Shopify listing says sourcing is limited to the United States.
- No source I could read confirms that Doba accepts a Swiss address or a card issued outside the U.S.
- One Shopify review reports payment-setup trouble ("could not use my business banking account"). Another, from a U.S. seller, lists cards, Payoneer and wallet balance as payment options. Both are single anecdotes.
- Doba's blog says its platform often requires verified business information for wholesale pricing, and that many suppliers want a resale certificate first.

Steps:
1. In your Shopify trial store, install Doba from its App Store listing ("Doba - AI Dropshipping"), or sign up at doba.com and connect the store afterwards.
2. Start the Basic trial. The listing shows a 7-day free trial. Doba's pricing page shows Basic as a 7-day trial for $0.99 and Standard as a 5-day trial for $0.99. Both bill the full plan when the trial ends (Basic is $59.99 a month). **Set a phone alarm for day 6 now.** // FILL: which trial you actually got, and its end date.
3. Record what sign-up asked for: country, business type, tax ID or EIN, resale certificate, phone, address format.
4. Open the payment screen. Record every payment method offered and whether a Swiss card is accepted for order payments.
5. Search the catalog for three product types you might sell. Record whether prices show, whether any product is unavailable to your account, and how many suppliers ask for a resale certificate or approval.
6. Send the support message below. Do not wait for the reply to carry on. Write the reply into `gate-results.md` when it arrives.

Result:
- **GO:** account created, a Swiss card or another documented payment method works for order payments, and at least three products you would sell are orderable without a resale certificate.
- **GO WITH LLC LANE:** the account works but the products you want need a resale certificate. Then the LLC, EIN and a state sales-tax permit sit on the critical path. The IRS says a foreign applicant can get the EIN by phone during the call, by fax in about 4 business days, or by mail in about 4 weeks. Formation, bank and payment-processor checks come on top of that. Keep building the store while they run.
- **NO-GO:** Doba refuses a Swiss account, refuses every non-U.S. payment method, or gates every supplier. Stop spending and tell Claude. The model changes. Next candidates to research: the U.S.-stock suppliers AutoDS lists ("Fulfilled by AutoDS" is described as using U.S.-based suppliers) and other U.S. dropship platforms. None is researched yet.

Support message (copy as is):

> Hello, I live in Switzerland and want to use Doba with a Shopify store that sells only to U.S. customers. Before I subscribe, please confirm: (1) Can I register with a Swiss address and a sole proprietorship? (2) Which payment methods can pay for orders, and are cards issued outside the U.S. accepted? (3) Do I need an EIN or a resale certificate to see wholesale pricing or to order from suppliers? (4) Is there a currency conversion fee, and what is the card payment fee on orders? (5) Can I downgrade from Basic to Limited before the trial bills? Thank you.

## Gate B - can Shopify pay you out and show U.S. dollars?

Steps, in the Shopify admin (menu names change; use the nearest equivalent):
1. Settings > Store details: set the store's country to Switzerland and the contact details you will really use.
2. Settings > Payments: see whether Shopify Payments can be activated. Third-party lists show Switzerland as supported and community posts say TWINT was added in June 2025, but no official page confirmed it for 2026. Do not complete identity checks until Gate A is GO.
3. Record the card rate shown for your account and the payout currency options. // FILL: your online card rate (the U.S. page shows 2.9% + 30 cents), and whether payouts can be CHF or USD.
4. Settings > Markets: add the United States as a market with U.S. dollar pricing. Record any currency conversion fee shown.
5. Settings > Taxes and duties: confirm the U.S. tax settings are visible. Leave collection off for now. See `store/shopify-setup.md`.

Result:
- **GO:** Shopify Payments can be activated for a Swiss-based store and can charge U.S. customers in USD.
- **GO WITH FALLBACK:** Shopify Payments is unavailable or cannot take USD. Use Stripe or PayPal. Shopify's Basic plan adds a 2% fee on third-party gateways. Set `--gateway-extra-pct 2` in `economics/landed_cost.py`.
- **NO-GO:** no gateway can pay a Swiss sole proprietor selling to U.S. customers. Stop and tell Claude. The LLC lane then becomes the route to a payment account.

## Gate C - the LLC clock (optional)

Only if you decided to fund the LLC lane. Formation, EIN, bank and payment-processor checks run one after another, so starting early matters. Read `entity/us-llc-runbook.md` first, then `entity/cpa-and-adviser-questions.md`. Do not form anything before the Swiss tax question has been put to an adviser.

## Order of operations

1. Open the Shopify trial.
2. Gate A, steps 1-5, then send the support message.
3. Gate B.
4. Fill `gate-results.md`. If either gate is NO-GO, stop.
5. Only then start the AutoDS trial (`research/autods-playbook.md`).
