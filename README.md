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

Install dependencies and run the full test suite:

```bash
pip install -r requirements.txt
pytest -q
```

## Opportunity discovery API

The discovery endpoint uses Mwmbl's anonymous free search tier by default, so
no API key or payment card is required. Anonymous access is limited to 1,000
requests per month and 1 request per second. Start the application with:

```bash
uvicorn app.main:app --reload
```

If you later create a Mwmbl developer key, set `MWMBL_API_KEY` in the server
environment to use the identified free tier (2,000 requests/month, 5 requests
per second). If `BRAVE_SEARCH_API_KEY` is configured, Brave takes precedence.
Do not enable pay-as-you-go billing unless you explicitly choose to do so.

Submit a search request:

```bash
curl -X POST http://127.0.0.1:8000/api/discover \
  -H "Content-Type: application/json" \
  -d '{"query":"legitimate game rewards programs","limit":10}'
```

The endpoint returns normalized candidates with source domains, discovery
timestamps, explainable text signals, and a heuristic confidence value. Results
are stored in a local review inbox and deduplicated by canonical URL; retrieve
them with `GET /api/discoveries`. These signals are not a legitimacy check.
Every result is explicitly marked `verified: false` and `review_required: true`;
nothing is clicked, registered, or acted on automatically. Search-provider
errors return HTTP 502. Mwmbl is used for a no-card prototype; confirm the
applicable data and API terms before any commercial launch.

## Scoring notes

The score is a heuristic based only on metadata supplied to the application. It is not proof that a platform is legitimate or that a reward will be paid. Users must verify eligibility, regional restrictions, and platform terms before participating.

## Safety boundaries

AutoEarn AI is an assisted decision-support tool. Website discovery and analysis must respect site terms, robots policies, privacy, and applicable law. The product will not automate gameplay, clicks, ad views, referrals, spam, or other activity intended to manipulate reward systems.


## Manual page-text extraction

A discovered candidate can be enriched with text copied from its public page.
AutoEarn does not fetch candidate URLs automatically. Submit the copied text
(maximum 20,000 characters) to:

```bash
curl -X POST http://127.0.0.1:8000/api/discoveries/1/extract \
  -H "Content-Type: application/json" \
  -d '{"page_text":"Earn €25 after completing the offer. Only residents of Germany are eligible. Participants must be 18+. Read the official terms and conditions."}'
```

The response identifies currency amounts, age hints, eligibility evidence,
and whether terms are mentioned. The extraction is stored with the candidate
and appears in `GET /api/discoveries`. It is explicitly unverified: users
must compare the extracted hints with the current official terms before
accepting an opportunity or taking any action.
