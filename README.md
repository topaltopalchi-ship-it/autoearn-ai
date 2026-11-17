# AutoEarn AI

A transparent opportunity discovery and reward-tracking workspace.

The first release is a local-first MVP. It helps users record opportunity metadata, compare opportunities with an explainable score, and track their own progress. It does not promise income or automate clicks, gameplay, spam, account creation, or platform activity.

## Current implementation

- HTTP(S)-only URL validation and canonicalization for duplicate detection.
- Removal of common tracking query parameters and URL fragments.
- Opportunity metadata validation, including eligible/excluded countries, minimum withdrawal thresholds, withdrawal currency, and payout methods.
- Human verification status with reviewer notes and timestamp; new entries remain pending until manually verified.
- Persistent SQLite source-candidate intake with canonical URL deduplication, pending-by-default review, and reviewer notes.
- Dashboard workflow to submit source candidates and manually approve or reject them; source metadata is recorded without scraping or interacting with external platforms.
- Backward-compatible SQLite schema migration for the new eligibility and payout fields.
- Explainable 0–100 scoring using reward clarity, terms clarity, source trust, region fit, and effort fit.
- Unit tests using Python's standard library.
- GitHub Actions workflow to run unit tests on pushes and pull requests.

## Source review API

- `POST /api/sources` records a public source candidate. Every new candidate is stored as `pending`.
- `GET /api/sources` lists candidates; use `?status=pending`, `?status=approved`, or `?status=rejected` to filter.
- `PATCH /api/sources/{id}/review` records a human decision (`pending`, `approved`, or `rejected`) and reviewer notes.
- Canonical source URLs are unique. Duplicate submissions return HTTP 409. The intake stores supplied metadata only; it does not crawl websites or verify claims automatically.

## Development

Requires Python 3.10 or newer.

Run the tests:

```bash
python -m unittest discover -s tests -v
```

## Scoring notes

The API dashboard completeness score is normalized to 0–100 from three recorded fields: terms clarity (40 points), eligibility information (30 points), and reward description (30 points). The separate `score_opportunity()` helper uses five explicit user-assessed dimensions (reward clarity, terms clarity, source trust, region fit, and effort fit). Neither score proves that a platform is legitimate or that a reward will be paid. Users must verify eligibility, regional restrictions, and platform terms before participating.

## Safety boundaries

AutoEarn AI is an assisted decision-support tool. Website discovery and analysis must respect site terms, robots policies, privacy, and applicable law. The product will not automate gameplay, clicks, ad views, referrals, spam, or other activity intended to manipulate reward systems.
