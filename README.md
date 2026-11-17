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
- Capability-scoped discovery adapter registry covering games/competitions, surveys/microtasks, freelancing/services, AI content/products, and reviewed additional categories.
- Adapter manifests declare categories, allowed domains, execution mode, rate limits, allowed actions, terms permission, and mandatory user approval for platform actions.
- Discovery results are checked against declared categories and domain allowlists; all discovered source records remain pending review.
- Conservative eligibility evaluator reports eligible/ineligible/unknown, evidence freshness, confidence, risk flags, estimated net reward, and a transparent ranking score.
- Automatic participation is blocked unless country eligibility, source review, opportunity verification, fresh evidence, reward, time, payment-probability, risk, and an official API mode are all present.
- Backward-compatible SQLite schema migration for the new eligibility and payout fields.
- Explainable 0–100 scoring using reward clarity, terms clarity, source trust, region fit, and effort fit.
- Automated pytest coverage for API routes, evaluator, adapters, RSS parsing, and supervised action persistence.
- GitHub Actions workflow to run unit tests on pushes and pull requests.

## Source review API

- `POST /api/sources` records a public source candidate. Every new candidate is stored as `pending`.
- `GET /api/sources` lists candidates; use `?status=pending`, `?status=approved`, or `?status=rejected` to filter.
- `PATCH /api/sources/{id}/review` records a human decision (`pending`, `approved`, or `rejected`) and reviewer notes.
- Canonical source URLs are unique. Duplicate submissions return HTTP 409. The intake stores supplied metadata only; it does not crawl websites or verify claims automatically.

## Discovery adapter contract

Implementations must register a local Python adapter with an explicit `AdapterManifest`. Each adapter returns `DiscoveredLead` records with provenance and observation timestamps. The registry rejects leads outside the adapter's declared categories or allowed domains. The framework does not crawl arbitrary websites, run source-provided code, or perform platform actions. New leads are converted to pending source candidates and require human review.

## Eligibility evaluation

`autoearn.evaluator.evaluate_candidate()` keeps missing country evidence as `unknown`, marks explicit country mismatches as `ineligible`, and flags stale or incomplete evidence. Ranking values are estimates, not proof of payment. Execution is only marked eligible for a tightly scoped official-API integration with complete current evidence; actual platform execution is not implemented by this evaluator.

## Development

Requires Python 3.10 or newer.

Run the tests:

```bash
python -m pytest -q
```

## Scoring notes

The API dashboard completeness score is normalized to 0–100 from three recorded fields: terms clarity (40 points), eligibility information (30 points), and reward description (30 points). The separate `score_opportunity()` helper uses five explicit user-assessed dimensions (reward clarity, terms clarity, source trust, region fit, and effort fit). Neither score proves that a platform is legitimate or that a reward will be paid. Users must verify eligibility, regional restrictions, and platform terms before participating.

## Safety boundaries

AutoEarn AI is an assisted decision-support tool. Website discovery and analysis must respect site terms, robots policies, privacy, and applicable law. The product will not automate gameplay, clicks, ad views, referrals, spam, or other activity intended to manipulate reward systems.

## Product direction: multi-category autonomous agent

The target product covers prize competitions, surveys/microtasks, freelancing/digital services, AI-assisted content/digital products, and additional categories after review. It is being developed as a supervised agent: discover and evaluate opportunities, rank by eligibility and realistic net return, then participate only through permitted official integrations. Sensitive actions require user approval. See [the autonomous-agent roadmap](docs/AUTONOMOUS_AGENT_ROADMAP.md) for the operating loop, safety contract, and phased delivery plan.

### Read-only RSS/Atom discovery

`PublicRssAdapter` supports explicitly configured public RSS 2.0 and Atom feeds over HTTPS. Feed hosts and discovered item hosts must match an exact allowlist; redirects are disabled, DNS answers resolving to non-public addresses are rejected, and payloads are capped at 1 MB. It extracts public listing metadata only. It does not infer payment legitimacy, verify eligibility, scrape full websites, or submit applications. All resulting leads remain candidates for review.

### Human-supervised action lifecycle

The core `SupervisionQueue` models action requests, explicit human approval/rejection, cancellation, completion evidence, and an audit-event trail. Requests are rejected unless the opportunity is eligible, the source has been approved, and supporting evidence is fresh. Even sensitive actions (applications, accepting terms, publishing, sharing personal data, spending, and withdrawals) remain pending until a human approves them. The HTTP layer exposes this state machine through owner-authenticated routes; it records workflow state only and does not execute platform actions.

### Durable supervision and audit storage

`SQLiteSupervisionStore` persists supervised action requests and audit events across process restarts. It enforces eligible opportunity + approved source + fresh evidence at creation, human-attributed approval/rejection, approval before completion, completion evidence, and terminal-state transition rules. Audit rows are append-only through this API. Owner-only HTTP routes now expose these operations after validating the configured owner token.

### Owner-authenticated supervision API

Set a cryptographically random `AUTOEARN_OWNER_TOKEN` environment variable of at least 32 characters before starting the service. Send it in the `X-AutoEarn-Owner-Token` header for owner-only operations. If the secret is absent, these operations fail closed with HTTP 503; missing or incorrect tokens receive HTTP 401.

The owner-only endpoints cover source approval/rejection, opportunity eligibility status and verification, and supervised action creation, approval, rejection, completion, listing, and audit retrieval. A supervised action can only be requested when its opportunity is marked eligible and verified, its source is approved, and the verification timestamp is no older than 30 days. This API records workflow state; it does not execute external platform actions. Deploy only behind HTTPS, keep the token out of source control and logs, and rotate it if exposed. This single-owner token is a basic deployment gate, not a replacement for multi-user identity, session management, CSRF protections, or a secrets manager.

### Owner-triggered RSS/Atom discovery

`POST /api/discovery/rss` fetches a configured public RSS/Atom feed through the read-only adapter. The caller must be authenticated as the owner and must supply an exact hostname allowlist for the feed and discovered item links. The adapter enforces HTTPS, public DNS/IP checks, no redirects, a 1 MB response cap, and a maximum item count. New listings are stored as pending source candidates; duplicate canonical URLs are skipped. Discovery never approves a source or submits an application.

### Owner-only private records

Task creation/approval/completion, reward-ledger writes and reads, and dashboard totals now require the owner token. The same owner authentication applies to source review, opportunity status/verification, and supervised action routes. Public health and public opportunity/source listings remain read-only. Configure `AUTOEARN_OWNER_TOKEN` before using the protected workspace.

The web workspace now includes an owner-token field (kept in the current browser session only) and a **Discover RSS feed** action. Enter the exact feed and listing hostnames in the allowlist prompt. Discovered listings are added to Source candidates as pending; they still require manual review. The owner token must also be configured on the server as `AUTOEARN_OWNER_TOKEN`.
