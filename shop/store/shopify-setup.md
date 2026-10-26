# Shopify setup (U.S. store, Doba fulfilment)

Menu names move around in the Shopify admin. Use the nearest equivalent. `// FILL:` marks a screen or value only your admin shows.

## 0. Before you start

- Gate A and Gate B in `model/day0-gates.md` are GO.
- Keep the store on the password page until step 12.
- Install only the apps listed in step 9. Each app asks for store and customer data.

## 1. Account and store

1. Sign up for the trial on the Basic plan. Note the date the $1/month offer ends. // FILL
2. Settings > Store details: store name `[BRAND]`, contact email `[EMAIL]` (a role address, not a personal one), business address `[ADDRESS]`. Use an address where you can receive mail. Email marketing law and Shopify both expect a real one.
3. Settings > Plan: confirm Basic.

## 2. Markets: United States only

1. Settings > Markets. Keep or create "United States". Currency USD. Language English.
2. Remove or disable any "International" market so non-U.S. buyers cannot check out. Doba sells U.S. stock only.
3. Settings > Shipping and delivery: delete shipping zones for every other country.
// FILL: if your store's base currency is CHF, set USD presentment for the U.S. market and read the conversion fee line.

## 3. Shipping

Doba bills a shipping fee per order, and the margin gate already counts it. Pick one:
- **Free shipping, price includes it (recommended).** One U.S. zone, rate $0.00. Say "Free U.S. shipping" on the product page. Simple for cold traffic.
- **Flat rate.** One U.S. zone, rate at least your average Doba shipping fee.

Write delivery language from supplier data, not hope: "ships within [X] business days" where X comes from the supplier record, and "typically [Y]-[Z] business days after shipping" until you have your own numbers. The FTC's Mail, Internet or Telephone Order Merchandise Rule expects a reasonable basis for stated ship times and a refund option if you cannot meet them. Verify with a professional.

## 4. Taxes

Settings > Taxes and duties.
- Leave U.S. sales tax **collection off** until a CPA confirms you have a filing obligation. Nexus is decided state by state, usually by sales totals and order counts. Shopify reports sales by state. Check them monthly. Questions are in `entity/cpa-and-adviser-questions.md`.
- Duties do not apply to stock already in the U.S.
- This is not tax advice. // FILL: your CPA's instruction.

## 5. Payments

Settings > Payments.
- Shopify Payments if Gate B allowed it. Enter identity and bank details yourself.
- Otherwise Stripe or PayPal. On Basic, a third-party gateway adds a 2% Shopify fee. Re-run the margin gate with `--gateway-extra-pct 2`.
- Turn on **test mode** for step 13, then turn it off before launch. // FILL: where test mode lives in your admin.
- Do not add TWINT. It is for Swiss customers and this store sells only to the U.S.

## 6. Checkout

Settings > Checkout.
- Contact by email only. Customer accounts optional.
- Marketing consent: leave unticked by default.
- Abandoned checkout emails: automatic. Use the copy from `email/abandoned-cart.md`.
- Tipping and order notes: off.

## 7. Notifications

Settings > Notifications. Edit "Order confirmation" and "Shipping confirmation":
- Put the real delivery window and `[EMAIL]` in the footer.
- Add: "If anything is wrong with your order, reply to this email."
Copy is in `email/`.

## 8. Policies and pages

- Settings > Policies: paste `pages/privacy-policy.md`, `pages/terms-of-service.md`, `pages/returns-refunds.md`, `pages/shipping-policy.md`. Replace every `[BRACKET]`. **Have a professional review them before launch.** With Claude's theme, copy the Refund and Shipping policy text from your live Returns and Shipping pages instead (`theme-guide.md` section 5), so policy and page agree.
- Online Store > Pages: with Claude's theme, create the five pages in `theme-guide.md` section 3 and leave their bodies empty, because the templates supply the text. Without the theme, create About, Contact and FAQ from `pages/`.
- Online Store > Navigation: footer menu with Shipping, Returns and Contact, plus About and FAQ with Claude's theme. Add Privacy and Terms too, unless the theme lists the policies itself (Claude's theme does, in the footer's bottom row).

## 9. Apps (minimum set)

1. **Doba**: import, inventory sync, order fulfilment. Open its settings and note the pricing rules, inventory sync and order flow. // FILL: whether orders submit to Doba automatically or wait for your approval.
2. A reviews app, only for real reviews from real buyers. Never import or write reviews yourself.
3. Nothing else at launch. Skip pop-ups, countdown timers, "recent purchase" notifications and trust-badge apps.

## 10. Theme and brand

- Use Claude's theme: connect it from GitHub, fill Store facts, preview with `theme-checklist.md` (`theme-guide.md`). The alternatives are `ai-store-builder.md` or a free Shopify theme.
- Logo and colours from `../brand/`.
- Design for phones first. Most social traffic arrives on one. Check every page on your own phone.
- Home page order: hero with the one problem, the product, three-step how it works, honest delivery and returns, FAQ.

## 11. Domain

Settings > Domains. Connect the `.store` domain you bought, or the free first-year `.store` domain some tools include. Make it primary. Use a role email on that domain. // FILL: your registrar's steps.

## 12. Pre-launch checklist

- [ ] Gate A and Gate B are GO
- [ ] Only the U.S. market is open
- [ ] Product copy matches the supplier listing and the claims log is done
- [ ] With Claude's theme: Store facts filled, promises in `theme-guide.md` section 7 checked, `theme-checklist.md` done
- [ ] No fake reviews, counters, "as seen on" logos or "X sold" claims anywhere
- [ ] Policies reviewed by a professional
- [ ] Test checkout done and test mode turned off (step 13)
- [ ] You understand what triggers a Doba order and where tracking comes back
- [ ] Footer shows a real contact address and email
- [ ] Domain connected, SSL active
- [ ] Password page removed (Online Store > Preferences)

## 13. Test checkout (no product ordered)

1. Turn on payments test mode.
2. On your phone, add a product to the cart and check out with the test card Shopify shows in test mode. Use a U.S. test address.
3. Confirm the USD price, the shipping line, the tax line, the confirmation email and the order in admin.
4. Do **not** fulfil it and do **not** let it reach Doba. Cancel and archive it.
5. Turn test mode off.

// FILL: if the test order reaches Doba on its own, cancel it inside Doba within the minute and tell Claude.
