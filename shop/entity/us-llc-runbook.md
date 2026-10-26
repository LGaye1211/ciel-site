# U.S. LLC runbook (foreign owner, Switzerland)

Not legal or tax advice. IRS details below were read from IRS.gov on 2026-10-17. Everything else comes from vendor blogs and is marked **unverified**. A cross-border CPA and a Swiss adviser come first (`cpa-and-adviser-questions.md`).

## Do you need it now?

You can run the store without it: open Shopify, Doba, AutoDS and EcomBos in your own name as a Swiss sole proprietor (`einzelfirma-steps.md`). The LLC helps when:
- Doba or its suppliers require a resale certificate, which needs an EIN and a state sales-tax permit (`model/day0-gates.md`, GO WITH LLC LANE).
- Shopify Payments or Stripe will not onboard you without a U.S. entity.
- You want a U.S. bank account and U.S. address for the business.

It costs money and creates yearly filings in two countries. Do not form it before the Swiss tax question has been answered by an adviser.

## Costs (vendor comparison pages; verify on each state's site)

| Item | Wyoming | New Mexico | Delaware |
|---|---|---|---|
| Filing | $100 | $50 | $110 |
| Yearly | $60 minimum annual report | $0 | $300-400 franchise tax (sources conflict) |
| Verdict | cheapest common choice | cheapest if it suits your CPA | skip |

Also: a registered agent (required, // FILL: price), a formation service ($79 basic plus state fee in one source; Doola $297 a year starter), your CPA. First-year total is roughly $130-400 before the CPA.

## Steps

1. **Adviser calls first.** Put the questions in `cpa-and-adviser-questions.md` to a U.S. CPA and a Swiss adviser. Write down the answers.
2. **Choose the state.** Wyoming or New Mexico unless the CPA says otherwise. Check the name in the state's business search. The name must contain "LLC" or "L.L.C.".
3. **Registered agent.** The state requires a U.S. address that receives legal mail. Pick an agent or a formation service that includes one.
4. **File the Articles of Organization online** with the Secretary of State. Keep the stamped copy. Typical approval takes days. // FILL: current processing time on the state site.
5. **Sign the operating agreement** (`operating-agreement-template.md`). A professional reviews it.
6. **Get the EIN.** A foreign applicant cannot use the online form (IRS Form SS-4 instructions). The ways:
   - **Phone:** 267-941-1099, not toll-free, 6 a.m. to 11 p.m. U.S. Eastern, Monday to Friday. The agent assigns the EIN during the call. Write it on the form, sign, keep a copy.
   - **Fax:** 304-707-9471 from outside the U.S. The IRS faxes the EIN back, generally within 4 business days. Include your fax number.
   - **Mail:** Internal Revenue Service, Attn: EIN International Operation, Cincinnati, OH 45999. About 4 weeks.
   - On line 7b (responsible party SSN or ITIN) write **"foreign"** or N/A if you have no SSN and cannot get one. An entry is required.
   - The responsible party must be an individual (you), not the registered agent.
7. **Bank account.** Wise Business, Mercury or Relay accept non-resident LLC owners according to vendor guides. Mercury is not open to every country. Banks want the EIN first. // FILL: which of them opens an account for a Swiss resident.
8. **Payments.** Stripe works with an EIN and passport, no SSN, per several vendor sources. Shopify Payments U.S. may reject non-resident LLC owners (one 2026 vendor article). PayPal Business: check its current rules. // FILL: test before you move the store.
9. **Move the store.** Update the legal business details in Shopify, Doba and the payment accounts so every name, address and number match the formation papers exactly. How Shopify transfers a payments account between entities is unverified. // FILL: ask Shopify support.
10. **Sales-tax permit and resale certificate.** Which state to register in is a CPA question. A resale certificate is a state document and the EIN is federal (one vendor page). Some states ask for an SSN or ITIN. // FILL
11. **Keep the money separate.** The LLC's money never mixes with yours. Pay yourself by documented transfer. Co-mingling can weaken the liability protection and creates reporting problems.

## Yearly duties

- **Form 5472 + pro forma Form 1120** (IRS Form 5472 instructions, reviewed 30 Apr 2026): a foreign-owned single-member U.S. LLC is a reporting corporation. It files Form 5472 when it has a reportable transaction with you, the foreign owner. Money you put in at formation and any draws are reportable, so plan to file every year. Ask the CPA whether any year truly qualifies for the no-transaction exception.
  - Filed with a pro forma Form 1120 with "Foreign-owned U.S. DE" written across the top. Only the LLC's name and address and items B and E on page 1 are required.
  - Due with the Form 1120. For a calendar-year LLC that is April 15, or October 15 with Form 7004 filed by April 15. // FILL: confirm on IRS.gov.
  - **Cannot be e-filed.** Fax 855-887-7737, or mail to Internal Revenue Service, 1973 Rulon White Blvd M/S 6112, Attn: PIN Unit, Ogden, UT 84201.
  - **Penalty: $25,000** for failing to file when due, plus another $25,000 for each 30-day period after 90 days of IRS notice. A substantially incomplete form counts as not filed.
- **State annual report** (Wyoming: minimum $60, due in the anniversary month) and registered agent renewal.
- **U.S. income tax** depends on whether the LLC has income effectively connected with a U.S. trade or business. Selling U.S. inventory to U.S. customers probably does. The CPA decides, including any Form 1040-NR. // FILL
- **Sales tax** by state once a nexus threshold is crossed. // FILL
- **FinCEN beneficial ownership report:** vendor sources say U.S.-formed entities were exempted by a March 2025 interim rule. // FILL: verify on fincen.gov.
- **Swiss side:** report the LLC and its income on your Swiss return. Swiss treatment of a U.S. LLC is unsettled (`cpa-and-adviser-questions.md`).

## Timeline (typical, not promised)

| Step | Time |
|---|---|
| Adviser calls | days |
| State filing | days (// FILL) |
| EIN | same phone call, or about 4 business days by fax, or about 4 weeks by mail (IRS) |
| Bank account | days to weeks (vendor sources) |
| Payment processor verification | days to weeks |

The EIN is the fast step. Bank and processor checks usually take longer.

## Do not

- Do not use a registered agent's address as your business's only real presence if a bank or processor will reject it. One vendor article says processors increasingly want proof of a U.S. operational presence. // FILL: ask before you pay.
- Do not copy another seller's operating agreement or terms.
- Do not start selling under the LLC's name before the EIN and bank account exist.
