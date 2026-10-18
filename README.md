# Dawn Dropship

A Shopify Online Store 2.0 theme for a small dropshipping store that sells to U.S. customers. It is Shopify's **Dawn 16.0.0** with a few changes. Dawn is copyright Shopify Inc. Its license is kept unchanged in `LICENSE.md`. That license allows use only for themes that work with Shopify, which is how this theme is used.

This branch contains only the theme, because Shopify's GitHub integration reads the theme folders at the branch root. The kit that goes with it (playbooks, policies, scripts) is on the `claude/great-cerf-xca3vw` branch under `shop/`.

## What is different from Dawn

- **Colors:** a calm palette (paper, ink, terracotta, soft teal) in the five color schemes. Every text and button pair clears the WCAG AA 4.5:1 contrast ratio.
- **Store facts:** a new settings group, Theme settings > Store facts. Business name, address, support email, reply time, shipping days, delivery window, free shipping, return days and refund days. New sections read these. A sentence whose fact is empty is hidden, so the site never states a number you did not enter.
- **New sections:** Store facts bar (header), Shipping and returns, FAQ, Policy page (shipping or returns), About page, Contact details.
- **New page templates:** About, FAQ, Shipping, Returns. The Contact template gains the contact details.
- **Home page:** hero, products, how it works, shipping and returns, FAQ. Product page: the vendor line is removed, because a supplier's name can show there, and the shipping and returns facts are added.
- **Footer:** the newsletter form, Follow on Shop and the country and language selectors are off by default. A Help menu uses your Footer menu.
- **Languages:** English only.
- **Removed:** Dawn's CI workflow, release notes and other languages.

## No fake proof, by design

This theme has no countdown timers, no "only N left" counters, no "recent purchase" popups, no invented ratings and no review badges. The product page does not show inventory counts. Do not add them unless they show true facts.

## Pages to create

Create these in Online Store > Pages. The handle matters, because other sections link to `/pages/returns`.

| Page title | Handle | Template |
|---|---|---|
| About | about | page.about |
| FAQ | faq | page.faq |
| Shipping | shipping | page.shipping |
| Returns | returns | page.returns |
| Contact | contact | page.contact |

Then add them to the footer menu (Online Store > Navigation > Footer menu). Shipping and returns text also belongs in Settings > Policies. Keep the two in step.

## Policy text

The Shipping and Returns pages hold template text. Have a professional review them before you publish.

## Checks run on this version

- Shopify Theme Check: no errors. Its 9 warnings are the same 9 Dawn 16.0.0 produces on its own.
- Every template and group checked against the schema of each section it uses.
- The new sections rendered against filled, empty and edge-case store facts with a Liquid engine (28 checks). That engine is close to Shopify's but not identical, so a preview in your store is the final check.
- Not tested in a live Shopify store from the environment that built it. Preview before you publish and run a test checkout.
