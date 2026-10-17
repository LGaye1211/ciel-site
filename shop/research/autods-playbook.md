# AutoDS research playbook (3-day trial)

Goal: leave the trial with **15 candidate products** in `economics/candidates.csv`. Not 150.

What AutoDS offers, per its own pages: a marketplace with demand filters, a trending products hub, a hand-picked section, and ad-spy tools. A Product Finding Hub add-on costs $14.97 a month on the official pricing page. // FILL: menu names in your dashboard may differ, so use the nearest equivalent. Whether the Hub is included in the trial is not stated anywhere I could read.

Trial: $0.99 for 3 days (official page), cancel any time. Start it only after Day 0 gates are GO and step 0 below is done. Set an alarm for 24 hours before it ends. Default plan: export, then cancel. Keep a paid plan only if you later decide to import through AutoDS. AutoDS does not list Doba as a supplier source, so it is not part of the Doba fulfilment path.

## Step 0 - before the clock starts (30 minutes, free)

1. Pick two or three areas to look in. Exclude regulated ones: supplements, cosmetics, kids' products, electronics with batteries or mains power, branded goods, anything medical.
2. Open Google Trends (United States, past 12 months and past 5 years), Reddit search and Discord search in tabs.
3. Collect 3-5 Reddit threads per area where people complain about a problem. Paste them into Claude with Prompt 1 below. Keep the ranked pain list.
4. Open `economics/candidates.csv`.

## Day 1 - find

Use the marketplace, trending and hand-picked areas. Apply filters in this order:
1. Ships from the United States. The product has to be orderable from U.S. stock, because Doba sells only U.S. stock. // FILL: the AutoDS location or fast-shipping filter name.
2. A sell price you could charge between $25 and $80. Under $25 the margin gate rarely passes. Over $80 is harder to sell cold.
3. Supplier cost plus shipping at most 50% of that sell price.
4. A demand signal that is growing or steady over 30 days, not a one-week spike.
5. No regulated categories.

Save every product that passes to a scratch list: title, link, supplier price, shipping, demand signal.

## Day 2 - score

If the Product Finding Hub is in your trial, use its scores for demand, competition and shipping time. Then run the **painkiller test** on your top 20. A product needs 4 of 5:
1. People complain about the problem unprompted (you saw it in Step 0 or in reviews).
2. It is hard to find in big-box stores, or the store version costs at least twice as much.
3. A viewer understands the benefit in the first 3 seconds of a clip.
4. The benefit can be shown without health claims or risky use.
5. Low return risk: no sizing, no fit, no compatibility traps, little to break.

Cut to 15. These are the ones that go to the Doba bridge.

## Day 3 - validate

For each of the 15:
1. Google Trends shape: steady or rising, not a single spike.
2. Meta Ad Library and TikTok Creative Center: how many sellers advertise it and for how long? An ad running for months suggests it earns money. Many identical stores suggests a crowded product.
3. Price check at Amazon and Walmart. If the same item is $10 there, drop it.
4. Run Prompt 3 in Claude for a score and a list of objections.
5. Fill `economics/candidates.csv` with AutoDS's cost and shipping if shown. The Doba numbers come in the bridge step.

Then take screenshots of the 15 and cancel or keep the plan.

## Prompts for Claude

**Prompt 1 - complaint mining**
> Below are [N] Reddit/Discord threads from [AREA]. Extract: (1) the 10 most repeated problems, ranked by how many people raise them, (2) the exact phrases people use to describe each problem, (3) what they have already tried and why it failed, (4) any product type that would solve each problem and be hard to find in a big-box store. Do not invent threads or quotes. If a point appears only once, say so.

**Prompt 2 - angle and objection pack**
> Product: [TITLE]. Supplier listing says: [PASTE LISTING TEXT]. Using only what the listing supports, give me: 5 problem-first angles, the 8 objections a skeptical U.S. buyer would raise, and a one-sentence honest answer to each. Flag every claim the listing does not support.

**Prompt 3 - candidate scoring**
> Score these 15 candidates from 1-5 on: pain intensity, ease to demo in 10 seconds, return risk, competition, and margin room at the sell price. Show a table and a one-line reason per cell. Mark any I should drop and why. Data: [PASTE CANDIDATES].

## Done when

`economics/candidates.csv` has 15 rows, `category_flag` filled where needed, and a screenshot folder for the 15 (kept on your own machine, not in this repo).
