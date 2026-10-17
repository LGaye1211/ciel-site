# buildyourstore.ai: run it, then fix it

The video's description names an AI store builder at buildyourstore.ai that makes "a Shopify store in under 2 minutes". It saves setup time. It does not produce a finished store.

What reviews say (affiliate and competing review sites, so treat as indicative):
- Generation is free. You still need a Shopify plan.
- A free `.store` domain for the first year, a theme and 10 pre-loaded dropshipping products come with it, plus AutoDS fulfilment access.
- A Pro tier costs $97 once or about $79 a month. The sources conflict. **Skip Pro.**
- Stores built from shared niche templates look alike. One review lists a cart theme bug on a paid tier.
- One reviewer puts the Shopify App Store rating near 3.5 across 42 reviews.

// FILL: confirm every price and inclusion on buildyourstore.ai before you click anything.

## Run

1. Open buildyourstore.ai. Enter the niche, the brand name from `../brand/names.md` and the colours from `../brand/palette.md`.
2. Connect your Shopify trial store when asked. Read the permissions screen before you accept.
3. Let it generate. Do not publish.

## Fix list (do all of it)

1. **Delete the pre-loaded products.** They come from the builder's catalog, most likely AliExpress items sourced through AutoDS, which Doba cannot ship. Only products that passed the Doba bridge and the margin gate go live.
2. **Strip fake social proof.** Remove countdown timers, "only 3 left" counters, "12 people viewing", "sold in the last 24 hours" pop-ups, "As seen on" logos, "10,000+ happy customers", star ratings without real reviews and invented testimonials. The FTC's 2024 rule bans fake reviews and testimonials, including AI-generated ones, and counters like these are misleading when untrue.
3. **Rewrite the copy** from the supplier listing only, using Prompt 2 in `../research/autods-playbook.md`. No health claims. No "guaranteed".
4. **Test the cart.** Add, change quantity, remove, check out, all on a phone. Fix the theme or switch themes if anything breaks.
5. **Audit the apps.** Admin > Apps. Remove anything you did not choose.
6. **Replace placeholder pages** with the files in `pages/`.
7. **Check shipping, returns and contact text** against `pages/shipping-policy.md` and `pages/returns-refunds.md`.
8. **Make it different.** Change the hero image, fonts and section order so it does not match every store from the same template.
9. **Check speed on a phone.** Load the home page on mobile data. // FILL: your target and tool.

## Do not

- Do not buy Pro to fix problems this list already covers.
- Do not let the builder publish, switch the password page off or connect a domain before the list is done.
- Do not keep any AutoDS or AliExpress product link the builder added.
