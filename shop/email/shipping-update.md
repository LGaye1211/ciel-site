# Shipping update messages

Edit these inside Shopify (Settings > Notifications). **Keep Shopify's own variables for order number, items, address and tracking** and change only the words around them. // FILL: copy the variable names from Shopify's default template, because they differ between templates and versions.

## Order confirmation - add this paragraph

```
Your order ships from a U.S. warehouse within [X] business days. After it ships, delivery is typically [Y]-[Z] business days. You will get a tracking link by email.
If anything is wrong with your order, reply to this email.
```

## Shipping confirmation - replace the intro

```
Good news: your order has shipped.
Track it here: [Shopify's tracking link variable]
Tracking can take up to [N] hours to show its first scan. Typical delivery is [Y]-[Z] business days.
Questions? Reply to this email.
```

## Delay notice (send by hand, from your support inbox)

Send as soon as you learn an order will miss the date you stated. The FTC's Mail, Internet or Telephone Order Merchandise Rule (verify with a professional) expects you to tell the customer and offer a way to cancel.

**Subject:** An update on your order [ORDER NUMBER]

```
Hi [FIRST NAME],

Your order [ORDER NUMBER] is running late. The new expected delivery is [DATE].
You can wait for it, or reply to this email and we will cancel and refund you in full.
We are sorry for the delay.

[BUSINESS NAME], [EMAIL]
```

## Delivered check-in (day after the tracking shows delivered)

**Subject:** Did your order arrive?

```
Hi [FIRST NAME],

Tracking shows your order [ORDER NUMBER] was delivered. If it is not what you expected, or anything is damaged, reply to this email with your order number and a photo. We will make it right.

[BUSINESS NAME], [EMAIL]
```

Rule: this email asks about problems first. It is not a review request. The review request comes later (`review-request.md`).
