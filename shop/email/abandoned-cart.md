# Abandoned cart flow (3 emails)

Trigger: a checkout started with an email and not completed. Use Shopify's abandoned-checkout email slot and keep the default checkout link variable from Shopify's own template. // FILL: the variable name in your admin.

No fake urgency anywhere: no countdown timers, no "only N left" unless it is the true stock count, no invented demand.

## Email 1 - 1 hour

**Subject:** You left something in your cart
**Preview:** Here is the link back

```
Hi [FIRST NAME],

You left [PRODUCT] in your cart. Your cart is still there:

[CHECKOUT LINK]

If you hit a problem at checkout, reply to this email and we will help.

[BUSINESS NAME], [ADDRESS]
Unsubscribe: [UNSUBSCRIBE LINK]
```

## Email 2 - 24 hours

**Subject:** Questions before you order?
**Preview:** The answers people ask for most

```
Hi [FIRST NAME],

Before you decide, the questions we hear most:

- How long does it take? Ships within [X] business days, typically arrives in [Y]-[Z] business days after shipping.
- Can I return it? Yes, within [X] days. [RETURNS LINK]
- [LISTED QUESTION 1]? [Answer from the listing.]
- [LISTED QUESTION 2]? [Answer from the listing.]

Your cart: [CHECKOUT LINK]
Anything else? Reply to this email.

[BUSINESS NAME], [ADDRESS]
Unsubscribe: [UNSUBSCRIBE LINK]
```

## Email 3 - 72 hours

**Subject:** Your cart is still here
**Preview:** Last note from us

```
Hi [FIRST NAME],

We saved your cart. This is our last reminder:

[CHECKOUT LINK]

[ONLY IF YOU DECIDE TO OFFER IT:] Use [CODE] for [X]% off. It works until [DATE].

[BUSINESS NAME], [ADDRESS]
Unsubscribe: [UNSUBSCRIBE LINK]
```

## Rules

1. Three emails at most per abandoned cart.
2. Check the margin gate before you offer any code. A discount lowers net per order and can fail the gate.
3. Do not send to anyone who has not given an email at checkout.
