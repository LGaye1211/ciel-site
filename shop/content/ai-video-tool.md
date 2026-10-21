# EcomBos Pro: settings, credits, fidelity test

**Verdict:** EcomBos stays the pick for paid video, but on the cheapest path it is an **upgrade, not a day-one cost**. Start with `free-video-stack.md`. Subscribe to **Pro, monthly, by card** only when a trigger fires: the free tools fail the fidelity test on 2 of 3 products, you cannot make a clip a day, or a product reaches 10 add-to-carts. Then treat the first month as a test. It is the video's tool, it bundles the models you need, and its terms say the output is yours to use commercially. Evidence is thin: the only review found is an affiliate publisher's, no Reddit or Trustpilot results turned up, and the terms name no company or country. The product lives at ecombos.ai (ecombos.com is a parked domain for sale).

## Account rules (from its terms)

- All sales final. Credits for a billing period do not roll over. Purchased credit packs do not expire.
- Chargebacks count as a violation and can get the account suspended. Contact support first.
- EcomBos can terminate an account immediately, for any reason, with no appeal. **Download every asset you want to keep.**
- Failed generations are refunded in credits automatically.
- Pay by card, monthly. Never annual.

## Plans (pricing page and one review)

| Plan | Monthly | Annual per month | Credits | Notes |
|---|---|---|---|---|
| Starter | $19 | $15 | 100 | Trial tier. The pricing page lists Marketing Studio as not included and lists UGC avatar videos only from Pro up. |
| **Pro** | **$49** | $39 | **300** | UGC avatar videos, Marketing Studio, 2 concurrent videos |
| Ultimate | $99 | $79 | 700 | 4 concurrent, 4K |
| Creator | $199 | $159 | 1,600 | |

The video's description lists a 25% off code. // FILL: whether it applies to month 1 and to Pro.

## Credit costs per generation (from one review; // FILL: confirm in the app)

| Model | Credits |
|---|---|
| GPT Image 2 | 2 |
| Seedream 4.5, Recraft v3 | 3 |
| Nano Banana Pro | 4 |
| **Seedance 2** (up to 15 s, with audio) | **10** |
| Runway Gen-4 | 16-32 |
| Runway Aleph | 22 |
| Kling 2.6 Pro | 28 |
| Kling 3.0 Pro | 30 |
| Veo 3.1 (8 s cap) | 35 (25 for Fast) |
| HeyGen UGC avatar video | 50-100 |

## Pro budget (300 credits)

| Use | Count | Credits |
|---|---|---|
| New Seedance 2 clips in the calendar | 18 | 180 |
| Retakes (about 50% of clips, since fidelity failures are common) | 10 | 100 |
| Product stills with GPT Image 2 | 10 | 20 |
| **Total** | | **300** |

That covers the 18 new clips and 8 re-cuts in `calendar-30-day.md`. There is no room for avatar videos or Veo clips. If you want daily new clips or avatars, move to Ultimate ($99, 700 credits) after the test month.

## Clip recipe (image-to-video)

1. Collect 3+ photos of the product from the Doba listing, at least 1000 px wide, different angles. No lifestyle photos with other branded items.
2. Upload them as the reference. Choose Seedance 2.
3. Prompt:

```
Image-to-video from the attached product photos. Keep the product exactly as in the photos: same shape, color, label and proportions. Scene: [SETTING]. Action: [ONE ACTION THE LISTING SUPPORTS]. Camera: [slow push-in / static / gentle orbit]. Duration: [8-12] seconds. No text overlays, no logos other than the product's own, no extra products. Natural light.
```

4. Keep hands out of frame or resting near the product. Hands holding rigid products often deform them in AI video.
5. Add the narrator voice-over from `scripts.md`, with on-screen text from your editor.
6. Run the fidelity checks below before you post anything.

## Fidelity test (run it on whichever tool you use, before the first post)

Goal: find out whether EcomBos can render your actual products without changing them. You never see the product, so a video that misrepresents it becomes refunds.

1. Take 3 shortlisted products. Make 3 clips each: (a) static product on a surface with a slow orbit, (b) a hand resting near the product, (c) the product doing its listed function.
2. Score every clip, 1 point per line:
   1. Label, logo and printed text are legible and identical to the photos for the whole clip.
   2. Shape and proportions stay the same from first frame to last.
   3. Color and material stay the same.
   4. Size relative to the hand, room or other objects is believable and consistent with the listed dimensions.
   5. The function shown is exactly what the listing supports and nothing more.
3. A clip passes with 5/5 on lines 1-3 and 4/5 or better overall. Anything that shows a function the listing does not support fails regardless of score.
4. **Pass:** every product has at least 2 of 3 passing clips. **Fail:** 2 or more products fail. Then switch tool.

Record the result in your own notes:

```
product A:  clip a __/5   clip b __/5   clip c __/5   verdict
product B:  ...
product C:  ...
overall:    PASS / FAIL    date:
```

Review sites list known AI-video failures: logos and labels morphing, shapes drifting, hands deforming the product, and the same product looking different from clip to clip. Expect some.

## If the free tools fail the test

1. Make photo-and-text videos from the supplier's photos (`free-video-stack.md`, Route A). They cannot misrepresent the product.
2. Or subscribe to EcomBos Pro and run the same test again.

## If the test fails on EcomBos: switch steps

1. Download every asset from EcomBos.
2. Do not renew. Cancel in account settings so you keep access to the end of the billing period.
3. Trial the next tool on the same 3 products with the same 5 checks. Candidates, all from vendor or affiliate listicles with no independent head-to-head test:
   - **Creatify**: about $33-39 a month, URL to video, product sometimes appears beside the avatar rather than in hand.
   - **HeyGen**: about $24-29 a month, strong presenters and languages, 3 free watermarked videos a month.
   - **Arcads**: about $77-110 a month, most realistic faces, talking heads only, about $11 a video.
   - **MakeUGC**: product in hand only on its $119 a month tier.
4. Update `calendar-30-day.md` credits for the new tool.

## Claude via MCP

EcomBos's pricing page lists "Claude and ChatGPT via MCP" on every plan. No source I could read explains the setup. // FILL: email support@ecombos.ai and ask for the MCP server URL and sign-in steps. If they give you a URL: claude.ai > Settings > Connectors > add custom connector > paste it > sign in. Then Claude can draft and generate in EcomBos for you. Not tested.

## Labels and rules

Read `claims-checklist.md` before the first post. Short version: label realistic AI people or scenes where the platform asks, never show an AI person as a real customer, and show only what the listing supports.
