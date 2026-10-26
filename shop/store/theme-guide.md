# Claude's theme: connect, fill, publish

The store's website is a Shopify theme, **Dawn Dropship**, on the `shopify-theme` branch of this repo. It is Shopify's Dawn 16.0.0 with a calm palette, a "Store facts" settings group, and sections for shipping, returns, FAQ and About. What changed from Dawn is listed in that branch's `README.md`.

Menu names move around in the Shopify admin. Use the nearest equivalent. `// FILL:` marks a screen only your admin shows.

| You | Claude |
|---|---|
| Connect GitHub to Shopify, type the Store facts, create five pages, paste the policies, preview on your phone, press Publish | Writes and edits the theme code on the branch. Runs Theme Check, a schema validator and render tests before each push. Rewrites copy and sections when you ask. |

**Not tested in a live Shopify store.** The theme passed Theme Check (no errors), a schema validator and 28 render checks from a build environment with no Shopify account. Your preview and test checkout are the real test. Run `theme-checklist.md` before you publish.

## 0. Privacy: decide before you connect

The branch is **public**. Once connected, Shopify saves every theme-editor change back to it. Store facts live in `config/settings_data.json`. Anything you type there becomes public, and git history keeps it even after you delete it.

Pick one:
1. **Role email, no address (default).** Use support@your-domain. Leave Postal address empty, or use a business address you are happy to publish. Never your home address.
2. **Private repo.** Create an empty private repository on GitHub, tell Claude its name, and Claude pushes the theme there. This needs the repo attached to the Claude session. If that is refused, use option 3.
3. **No GitHub link: the zip route** (section 9). Nothing is written back to GitHub. Every Claude update is a new zip for you to upload.

## 1. Connect

1. Shopify admin > Online Store > Themes > Add theme > Connect from GitHub.
2. Authorize Shopify on GitHub. Choose repository `LGaye1211/ciel-site`, branch `shopify-theme`.
3. A new **unpublished** theme appears. Do not publish yet.

Shopify reads only a branch whose root holds the theme folders, which is why the theme has its own branch. Reconnecting the same branch creates a second theme; delete the old one.

While the theme is unpublished, Claude's pushes to the branch update it. Once it is **published**, a push changes the live store at once. After you publish, Claude puts changes on a second branch first (section 8).

## 2. Store facts

Theme editor > Theme settings (paintbrush) > Store facts. Every field is optional. **An empty field hides the sentence that uses it.** Nothing the site says comes from a guess.

| Field | Enter | Source |
|---|---|---|
| Business name | the name you sign policies with | Sole proprietor: the trade name from `../entity/einzelfirma-steps.md` step 8. LLC: its exact name. Empty hides "Who runs this". |
| Postal address | optional, see section 0 | |
| Support email | role address | the domain you connect (`shopify-setup.md` step 11) |
| Reply within (business hours) | a time you will keep | your own routine, `../ops/daily-checklist.md` |
| Order ships within (business days) | the supplier's handling time | the product's Doba listing; if products differ, the slowest |
| Delivery from / to (business days) | transit time after shipping, both ends | Doba's stated window; until you have your own orders, the slowest product |
| Free shipping to U.S. addresses | tick only if the Shopify rate is $0.00 | `shopify-setup.md` step 3 |
| Return window (days) | your policy | must equal the Returns policy text |
| Refund issued within (business days) | your policy | must equal the Returns policy text |

One number, three places: the supplier record, this setting, and the policy copy in Settings > Policies (section 5). Change one, change all. A stated ship time needs a reasonable basis (`shopify-setup.md` step 3).

## 3. Create the five pages

Online Store > Pages > Add page. The handle matters, because sections link to `/pages/returns`.

| Title | Handle | Theme template |
|---|---|---|
| About | `about` | about (file `page.about`) |
| FAQ | `faq` | faq |
| Shipping | `shipping` | shipping |
| Returns | `returns` | returns |
| Contact | `contact` | contact |

Leave the body empty on About, FAQ, Shipping and Returns. Their templates supply the text and do not show anything typed in the body. Text typed on Contact shows above the form. Set the handle under Search engine listing > Edit. If the store already has a Contact page, open it and set its template. // FILL: how your admin labels templates in the dropdown.

On the About page, open the section in the editor and write a short true introduction: what you sell, what problem it solves. No invented founder story, team, awards or years in business.

## 4. Menus

Online Store > Navigation (Content > Menus in newer admins) > Footer menu: add About, FAQ, Shipping, Returns, Contact. The footer's Help column uses that menu.

## 5. Policies

Settings > Policies. Shopify links these from checkout, and the theme lists them in the footer's bottom row.

- **Refund policy and Shipping policy:** open your Returns and Shipping pages in Preview, copy the text, paste it into the matching policy. The policy then says exactly what the page says. Do this after the Store facts are final, and again whenever a fact changes.
- **Privacy policy and Terms of service:** paste `pages/privacy-policy.md` and `pages/terms-of-service.md`. Replace every `[BRACKET]`.
- **A professional reviews all four before launch.**

## 6. Home, product pages, brand

- **Home.** The hero says "Simple fixes for everyday problems" as a placeholder. Replace it with the one problem your first product solves (`../brand/voice.md`). The "How it works" row says the order ships from a U.S. warehouse. That is true only for Doba U.S.-stock products.
- **Products.** Import them through Doba, or from `products.csv`. Vendor lines are off on the product page and in product grids, so the Vendor field (often the supplier's brand) is not shown. Do not add an inventory counter block.
- **Logo and favicon.** Theme settings > Logo and Favicon. Prompts are in `../brand/logo-prompts.md`.
- **Social links.** Shown in the footer only if you fill them in Theme settings > Social media. Leave empty until the accounts exist.
- **Colors.** Palette A from `../brand/palette.md`, already set. Change colors in Theme settings > Colors, and keep text and button pairs at 4.5:1 contrast or better.

## 7. Check the promises, then preview

The template text makes promises without any setting. You must be able to keep each one. Check them against Doba's terms and `../ops/doba-order-sop.md`:

- Orders ship from U.S. warehouses and the store holds no stock. Said in the header bar, Shipping and returns, About and FAQ (each has a toggle), on the Shipping page, and in the home "How it works" (edit that text in the editor, or ask Claude). Change it for any product that ships from elsewhere.
- The store ships to U.S. addresses only (FAQ, Shipping page). This matches the single U.S. market in `shopify-setup.md` step 2.
- "Change or cancel: yes, until it ships" (FAQ). Does Doba let you cancel in time? // FILL: Doba's cancellation rule.
- If an order will miss the stated time, the buyer can wait or cancel for a full refund (Shipping page, Late orders). Refund and chargeback handling is in `../ops/refund-chargeback-sop.md`.
- Damaged, defective or wrong items get a replacement or refund (FAQ, Returns page).
- "We never write fake reviews" (About). Keep it true.

Then follow `theme-checklist.md` on your phone. Preview shows what customers see. The editor shows extra hints for empty sections; customers never see those.

## 8. Test checkout, publish, update

1. Test checkout in test mode: `shopify-setup.md` step 13.
2. Themes > the connected theme > Publish. Then remove the password page (`shopify-setup.md` step 12).
3. **After launch, how Claude changes the site:**
   - Claude pushes changes to a second branch, `shopify-theme-next`, which you connect as another unpublished theme (same steps as section 1). You preview it. If it is good, Claude merges it into `shopify-theme` and the live theme updates. Claude asks before it pushes a new branch.
   - Claude never rewrites `config/settings_data.json` on a live theme unless you ask. It holds your Store facts and editor changes. A merge keeps the live branch's copy.
   - If you edit in the theme editor, Shopify commits to `shopify-theme`. Claude pulls before it edits.
   - Every change passes Theme Check, the validator and the render tests first (`theme-tools/README.md`).

**Optional: Shopify connector.** Connect it in claude.ai if you want Claude to rewrite product copy and read orders. Its tools reach products, orders and customers. Whether it reaches pages, collections or themes is unverified.

## 9. If the GitHub link fails: the zip route

1. Ask Claude for `shopify-theme.zip`, and Claude attaches it. Or build it yourself: download the branch from `https://github.com/LGaye1211/ciel-site/archive/refs/heads/shopify-theme.zip`, then
   ```
   python build_theme_zip.py ciel-site-shopify-theme.zip -o shopify-theme.zip
   ```
   (Windows: `py`.) The script finds the theme inside GitHub's wrapper folder and writes the seven theme folders at the zip root.
2. Online Store > Themes > Add theme > Upload zip file.
3. Continue from section 2. Updates mean a new zip each time, and the old theme's Store facts do not carry over. Copy them first.

The zip keeps Dawn's `LICENSE.md` at its root, because Dawn's license asks that its notice travel with copies. If Shopify refuses the upload, rebuild with `--no-license`. // FILL: whether your admin accepts it.

## Unverified

- Behavior in a live store: no Shopify account was available to the build environment.
- The Shopify GitHub integration details above come from Shopify's documentation and third-party guides, not from a connection I made.
- Whether the Shopify $1 trial offer and Shopify Payments exist for a Swiss account (`../model/day0-gates.md`).
- How your admin labels the page templates and where it keeps Navigation.
- Whether the connector reaches themes, pages and collections.
