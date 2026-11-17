# Preliminary platform screening: Azerbaijan

**Research date:** 2026-11-17  
**Scope:** Publicly documented country eligibility, payout conditions, and automation permission for a person operating from Azerbaijan. This is a research snapshot, not legal or tax advice and not proof that an individual account will pass onboarding.

## Decision summary

| Platform | Country status for Azerbaijan | Payout evidence | Agent/automation status | Intake decision |
|---|---|---|---|---|
| Upwork | General eligibility page says it serves freelancers in 180+ countries and lists restricted locations; Azerbaijan is not among the named exclusions. Its local-currency help page includes Azerbaijan in the EUR group. Neither fact guarantees a specific account or withdrawal method. | Upwork documents Direct to Local Bank at USD 0.99 per transfer and Payoneer/PayPal as possible methods; it says available methods vary by account and location. Confirm the exact method in the account before recording payout as supported. | Unapproved bots, scraping, auto-refresh and automated page interaction can lead to restrictions. Upwork says an API key must be requested and reviewed; even an API key does not authorize every action. | **Candidate / manual-assist only.** Country is provisionally not excluded by the general list; payout needs account-level confirmation; no automated participation until written API/use-case approval and exact scope are recorded. |
| Toloka | The current geographic restrictions page lists restricted and unsupported jurisdictions. Azerbaijan is not named in those lists, but omission is not affirmative proof of onboarding or task availability. Task-level country restrictions can still apply. | Toloka worker documentation describes Payoneer and PayPal among payout methods, with availability and limits depending on country/provider. No source reviewed here conclusively confirms the Azerbaijan-specific payout route or current minimum for an Azerbaijan account. | Toloka states that project-level requirements may restrict generative-AI tools and third-party assistance. General account eligibility does not grant permission to automate task completion. | **Needs recheck / manual only.** Ask Toloka support to confirm Azerbaijan onboarding, available payout rail, minimum and fees; each project must separately permit AI assistance. |
| Fiverr | The reviewed payout help page says payout methods have different location restrictions and directs users to verify provider coverage. It does not establish Azerbaijan-specific seller eligibility. | Published general minimums: PayPal USD 1; Payoneer bank transfer USD 20 (USD 1 fee); Payoneer account USD 10 (USD 3 fee). These are platform-level figures, not proof that a method works in Azerbaijan. | No explicit permission for an autonomous agent to operate a seller account or submit work was established in this review. | **Unknown / manual only.** Confirm seller onboarding, KYC and a usable payout method directly; do not automate account or order actions. |

## Evidence register

### Upwork

- Country eligibility: https://support.upwork.com/hc/en-us/articles/211067778-Who-s-eligible-to-join-and-use-Upwork
  - Reviewed 2026-11-17. Upwork says it supports freelancers in 180+ countries and lists specific restricted locations, including Iran, North Korea, Cuba, and Syria (payment-partner restrictions). Azerbaijan is not named in that list.
  - Interpretation is deliberately limited: absence from the named list is not a guarantee of account acceptance.
- Local currency: https://support.upwork.com/hc/en-us/articles/211068028-How-to-pay-in-your-local-currency
  - Azerbaijan appears in the EUR group. This identifies a local-currency option, not necessarily the exact payout rail or bank availability.
- Payouts: https://support.upwork.com/hc/en-us/articles/211060918-How-to-get-paid-on-Upwork
  - Reviewed 2026-11-17. Direct to Local Bank (outside the U.S.) is listed at USD 0.99 per transfer; PayPal and Payoneer are also listed as possible providers. Upwork explicitly says options vary and change.
- Automation: https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly
  - Reviewed 2026-11-17. Upwork warns against unauthorized bots, scraping and automated interactions; it instructs users to request an API key for a reviewed use case. API access remains limited to the approved scope.

### Toloka

- Geographic eligibility: https://toloka.ai/legal/eligibility-and-geographic-restrictions
  - Last updated 2026-05-27; reviewed 2026-11-17. Azerbaijan does not appear in the page's named restricted or unsupported lists. The page says additional screening may apply and project-level restrictions can narrow task access.
- Worker payout documentation: https://github.com/Toloka/docs-tolokers/blob/main/en/common/pay/about.md
  - Reviewed 2026-11-17. Lists PayPal, Payoneer, Papara and QIWI with country/provider-specific availability, fees and thresholds. The reviewed material does not establish the Azerbaijan-specific method/threshold.
- Project-level AI/third-party assistance restrictions are described on the geographic eligibility page. A task must be checked individually; do not infer that general platform access permits an agent to complete tasks.

### Fiverr

- Payout methods: https://help.fiverr.com/hc/en-us/articles/360010530058-Withdrawing-your-earnings-managing-payout-methods
  - Reviewed 2026-11-17. Fiverr lists PayPal, Payoneer bank transfer and Payoneer account with general minimums and fees, while warning that provider location restrictions differ. Fiverr Revenue Card is discontinued for new users and should not be treated as a viable new payout method.
  - This source does not confirm that a seller in Azerbaijan can onboard or use any specific payout method.

## Required follow-up before approval

1. Obtain a current, written or account-visible confirmation that an Azerbaijan-resident individual can onboard and complete identity verification.
2. Confirm the exact payout provider available to that account, account-holder name rules, currency, minimum, fees, FX spread, and transfer timing.
3. Save the official terms and policy URLs, access date, short excerpts, and reviewer.
4. For AI use, obtain platform/API permission for the exact use case and actions. A public API, general integration, or permission to use AI as a drafting aid is not permission for autonomous submission.
5. Keep every platform in `pending` or `needs_recheck` until all required evidence is complete. Never use VPNs, false residency, borrowed accounts, or payment-routing workarounds to evade restrictions.

## Product integration note

This file is a research input only. It does not create approved adapters, enable scraping, authorize browser automation, or mark any platform as execution-ready. The existing evaluator should keep country or payout facts as `unknown` until the account-specific evidence is recorded. All real submissions and sensitive actions remain behind the existing owner-confirmation gate.
