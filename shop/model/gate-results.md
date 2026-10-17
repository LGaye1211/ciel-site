# Gate results

Template. Copy it into your own notes if you want detail. **This repo is public: keep yes/no answers and fees here, never personal data.**

| Gate | Question | Answer | Date |
|---|---|---|---|
| A1 | Doba account created from a Swiss address? | | |
| A2 | Business verification, EIN or resale certificate demanded at sign-up? | | |
| A3 | Payment methods offered for orders | | |
| A4 | Swiss card accepted for order payments? | | |
| A5 | Products orderable without a resale certificate (count of 3 tested) | | |
| A6 | Doba trial end date and plan it will bill | | |
| A7 | Doba support reply, in one line | | |
| A8 | Doba card payment fee and currency conversion fee | | |
| B1 | Shopify Payments can be activated for a Swiss store? | | |
| B2 | USD pricing for the U.S. market works? | | |
| B3 | Online card rate shown | | |
| B4 | Payout currency options | | |
| B5 | Currency conversion fee shown | | |
| B6 | TWINT visible (not needed for U.S. sales)? | | |
| C1 | LLC lane started? State chosen? | | |

**Gate A:** GO / GO WITH LLC LANE / NO-GO
**Gate B:** GO / GO WITH FALLBACK / NO-GO
**Decision:** continue to `research/autods-playbook.md` / stop and tell Claude

After the gates, copy A8 and B3-B5 into `economics/landed_cost.py` flags: `--doba-card-pct`, `--pay-pct`, `--pay-fixed`, `--fx-pct`.
