# Theme checklist: phone preview QA

Run this on your own phone, in the draft theme's Preview (not the editor). Do it once on mobile data. Any fail: send Claude the page, what you saw and a screenshot.

## Facts

- [ ] Every Store facts number equals the supplier record and the policy text
- [ ] The header bar shows only true lines. "Free U.S. shipping" appears only if the Shopify shipping rate is $0.00
- [ ] No sentence has a gap, such as "within  of payment"
- [ ] No editor hint shows in Preview ("Open Theme settings...", "Template text. Have a professional review...")
- [ ] Promises in `theme-guide.md` section 7 are checked against Doba

## Home

- [ ] The hero names one real problem. The placeholder "Simple fixes for everyday problems" is gone
- [ ] The product grid shows only products that passed the margin gate, in USD
- [ ] "How it works" reads true
- [ ] The Shipping and returns cards show your numbers
- [ ] FAQ questions open and close on tap
- [ ] Nothing is cut off or overlaps, also on a narrow screen

## Product page

- [ ] Images swipe and load. No supplier logo, watermark or other store's name in any image
- [ ] Price in USD. A "was" price appears only if it was a real earlier price
- [ ] Add to cart works and the cart count changes
- [ ] Variants change price and image
- [ ] The description matches the supplier's specifications. No health claims, no "guaranteed"
- [ ] The Shipping and returns block matches Store facts
- [ ] No vendor name, stock counter, "people viewing" or "sold" claim

## Cart and checkout

- [ ] Change quantity, remove an item, subtotal updates
- [ ] Test checkout (`shopify-setup.md` step 13): USD, correct shipping line, confirmation email arrives
- [ ] The test order is cancelled and archived, and never reached Doba

## Pages

- [ ] About, FAQ, Shipping, Returns, Contact open from the footer with no 404
- [ ] About has no invented story, team, awards or years in business
- [ ] The contact form sends and the message reaches your support inbox
- [ ] Privacy, Terms, Refund and Shipping policies open from the footer
- [ ] The Shipping and Returns pages say the same as the policies

## No fake proof (scan every page)

- [ ] No countdown, "only N left", "recent purchase" popup, star rating without real reviews, "as seen on", "X sold" or invented testimonial

## Phone basics

- [ ] Menu and cart open and close
- [ ] Text is readable without zooming and buttons are easy to hit with a thumb
- [ ] Landscape does not break the layout
- [ ] The home page loads in a time you accept on mobile data. // FILL: your target and tool

## Before Publish

- [ ] Logo and favicon set
- [ ] Social links are real accounts, or empty
- [ ] Policies reviewed by a professional
- [ ] The rest of `shopify-setup.md` step 12 is done: domain, SSL, then remove the password page
