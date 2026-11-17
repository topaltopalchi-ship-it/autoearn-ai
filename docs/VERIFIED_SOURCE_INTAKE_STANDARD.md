# Verified opportunity source intake standard

This document defines how AutoEarn AI should curate sources before they are enabled for discovery. It is a review standard, not a directory of endorsed platforms. A source is not trusted merely because it is popular, has a polished website, or advertises rewards.

## 1. Source record

Record the following fields for every candidate source:

| Field | Required evidence |
|---|---|
| Source name and canonical URL | Official website or platform-owned documentation |
| Operator/legal entity | Terms, privacy notice, company/legal page |
| Opportunity categories | Published program or task documentation |
| Country availability | Explicit country/region list or written platform confirmation |
| Age and identity requirements | Official eligibility/KYC documentation |
| Payout methods | Official payout/help documentation |
| Payout currencies | Explicit supported currency list |
| Minimum withdrawal | Official payout threshold, including currency |
| Fees and conversion | Official fee schedule; mark unknown if not published |
| Payment timing | Official payout schedule and any hold/approval period |
| Automation policy | Terms/API documentation explicitly permitting the intended agent assistance |
| API and scopes | Official developer documentation and exact API host/scopes |
| Evidence checked at | UTC timestamp and reviewer |
| Evidence URLs and excerpts | Direct links and short supporting excerpts |
| Review decision | pending, approved, rejected, or needs_recheck |
| Recheck due | Date based on how quickly the policy or payout facts can change |

Never infer country eligibility from language, currency, website accessibility, or a payment processor's global presence. If the platform does not explicitly document a country, record it as unknown.

## 2. Evidence hierarchy

Use evidence in this order:

1. Current official terms, help-center articles, payout schedules, country lists, and developer/API documentation.
2. Written support response from the platform, with date and ticket/reference (do not store private personal data).
3. Reputable independent reporting for context only; it cannot replace official eligibility, payout, or automation evidence.
4. User reports and community discussions as risk signals only, never as proof of payment or official permission.

For each material claim, preserve the URL, access date, and a concise excerpt. A claim without evidence remains unknown.

## 3. Automation permission gate

A source may be marked automation-capable only when all of these are documented:

- The platform explicitly allows the relevant automated-agent use, or its official API terms clearly authorize the exact action.
- The API is official and the required scopes are documented.
- The adapter uses exact hostnames and narrowly scoped actions.
- Rate limits and data-use restrictions are recorded.
- Human approval remains required for submissions, contracts, publishing, personal-data sharing, spending, account changes, and withdrawals.

A general API, public webpage, or permission to use ordinary integrations does not automatically authorize autonomous participation. If wording is ambiguous, use manual or assist mode and request clarification from the platform.

## 4. Risk and rejection rules

Reject or flag for manual investigation any source that requires:

- Upfront payment, deposits, paid access to unlock a promised reward, or purchase of a package to withdraw.
- Fake identities, fabricated survey answers, multiple-account abuse, referral manipulation, fake engagement, ad-view automation, or gameplay/reward manipulation.
- CAPTCHA bypass, access-control evasion, credential sharing, or undocumented endpoints.
- Sharing passwords, seed phrases, private keys, or payment-card details with the source or agent.
- Unverifiable operator identity, contradictory payout claims, or unclear withdrawal conditions.

A source's own marketing claims do not independently verify legitimacy or payment history.

## 5. Country and payout decision

Evaluate country eligibility separately from payout availability:

- `eligible`: an official current source explicitly includes the configured country.
- `ineligible`: an official current source explicitly excludes it, or the required payout method is unavailable there.
- `unknown`: evidence is missing, ambiguous, stale, or only indirectly inferred.

Record payout method, currency, minimum withdrawal, fixed/percentage fees, conversion fees, and payment timing independently. Do not combine amounts across currencies. Calculate estimated net reward only when the necessary values are known; otherwise keep the result unknown and block automated execution.

## 6. Review lifecycle

1. New sources enter `pending`.
2. A reviewer collects official evidence and fills the source record.
3. Approve only when operator, country, payout, terms, and intended automation permission are adequately supported.
4. Use `needs_recheck` when material facts become stale, links break, terms change, or users report credible payment/eligibility issues.
5. Rejected sources remain rejected unless new authoritative evidence justifies a fresh review.
6. Every decision records reviewer, timestamp, reason, and evidence references.

Recommended recheck interval: 30 days for country/payout/terms facts and 7 days for time-sensitive campaigns. Recheck sooner after a platform announcement or credible incident.

## 7. Starter review worksheet

Copy this worksheet for each candidate; do not prefill facts from memory or marketing claims.

- Source name:
- Canonical URL:
- Operator/legal entity:
- Category:
- Official terms URL:
- Country evidence URL:
- Country decision: unknown
- Age/KYC requirements:
- Payout methods:
- Payout currencies:
- Minimum withdrawal:
- Fees/conversion:
- Payment timing:
- Automation permission URL and exact wording:
- Official API URL, host, and scopes:
- Known risks:
- Evidence checked at (UTC):
- Reviewer:
- Decision: pending
- Recheck due:
- Notes:

## 8. Product safety invariant

Discovery may collect public listing metadata from explicitly approved sources, but it must not silently approve a source, infer eligibility, promise earnings, or submit work. Unknown facts lower confidence and keep execution disabled. Real participation remains behind a reviewed official adapter and explicit owner approval.
