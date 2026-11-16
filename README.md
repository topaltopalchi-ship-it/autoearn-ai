# AutoEarn AI

A transparent opportunity discovery and reward-tracking workspace.

The first release is a local-first MVP. It helps users record opportunity metadata, compare opportunities with an explainable score, and track their own progress. It does not promise income or automate clicks, gameplay, spam, account creation, or platform activity.

## Current implementation

- HTTP(S)-only URL validation and canonicalization for duplicate detection.
- Removal of common tracking query parameters and URL fragments.
- Opportunity metadata validation.
- Explainable 0–100 scoring using reward clarity, terms clarity, source trust, region fit, and effort fit.
- Unit tests using Python's standard library.
- GitHub Actions workflow to run unit tests on pushes and pull requests.

## Development

Requires Python 3.10 or newer.

Run the tests:

```bash
python -m unittest discover -s tests -v
```

## Scoring notes

The score is a heuristic based only on metadata supplied to the application. It is not proof that a platform is legitimate or that a reward will be paid. Users must verify eligibility, regional restrictions, and platform terms before participating.

## Safety boundaries

AutoEarn AI is an assisted decision-support tool. Website discovery and analysis must respect site terms, robots policies, privacy, and applicable law. The product will not automate gameplay, clicks, ad views, referrals, spam, or other activity intended to manipulate reward systems.

## Automation policy and giveaway classification

Each opportunity can record its automation policy (allowed, prohibited, or unknown), CAPTCHA requirement, opportunity category, and the source/evidence used for review. Unknown policy or CAPTCHA status is treated as manual-only. A site that prohibits automation is excluded from automation eligibility. CAPTCHA-protected opportunities are never marked auto-eligible.

Free giveaways and skill contests may be marked auto-eligible only when automation is explicitly recorded as allowed, CAPTCHA is explicitly recorded as absent, a non-unknown evidence source is selected, and a supporting evidence URL or reviewer note is supplied. Evidence is still user-provided and must be checked by a person; the application does not independently verify that a website's terms permit automation. Paid lotteries and betting remain manual-only and are not automated. These labels are not legal advice or proof of eligibility, and prizes are not guaranteed income.

The policy classifier does not browse, submit forms, place bets, pay entry fees, solve CAPTCHAs, or bypass robots/anti-bot controls. Missing or uncertain evidence fails closed.
