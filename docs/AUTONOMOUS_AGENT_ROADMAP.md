# AutoEarn AI — Multi-category autonomous agent roadmap

## Product decision

The product covers **all opportunity categories**, not a single vertical. Discovery and ranking are category-agnostic; execution is delegated to narrowly scoped adapters that declare exactly what they are allowed to do.

Initial category registry:
1. **Games and competitions with prizes** — only official competitions and platform-authorized integrations. No gameplay automation, score manipulation, botting, or reward-system exploitation.
2. **Surveys and microtasks** — only tasks whose terms permit assistance/automation. Never fabricate demographic answers, identities, or task completion.
3. **Freelancing and digital services** — discover paid briefs, prepare drafts or deliverables, and support submission through permitted APIs/workflows. The user approves public submissions and contractual commitments.
4. **AI-assisted content and digital products** — discover legitimate paid opportunities and prepare original work. The user approves publication, licensing, and client commitments.
5. **Other categories** — admitted only after policy, legal, payout, and automation-capability review.

## End-to-end operating loop

1. Discover candidate sources through official APIs, public feeds, curated directories, and user-added URLs. Respect terms, robots directives where applicable, rate limits, and privacy. No stealth scraping or access-control bypass.
2. Normalize each opportunity and preserve source URL, observation time, evidence snippets, terms URL, country eligibility, payout method/currency/minimum, expected effort, deadline, and source freshness.
3. Evaluate eligibility for the user's explicitly configured country/profile. Missing facts are **unknown**, never assumed eligible.
4. Estimate net hourly return, payment probability, risk, effort, and automation feasibility. Keep advertised reward separate from independently verified payout history.
5. Recommend and rank opportunities with an explanation and confidence level.
6. Execute only through a registered adapter with explicit capabilities. Modes: manual, assist, and official_api. Unknown adapters default to manual.
7. Require user approval for account creation, accepting terms/contracts, spending money, submitting public work, sharing personal data, changing account settings, and initiating withdrawals.
8. Record every decision/action in an append-only audit trail; support pause/kill switch, per-adapter limits, retries, and a dry-run mode.
9. Reconcile completed work and actual payments separately from estimates.

## Ranking model

Rank candidates using configurable weighted factors:
- Eligibility certainty and country fit
- Expected net return and net hourly return
- Probability and evidence of payment
- Source trust and terms clarity
- Time/effort, deadline, and task complexity
- Legal, privacy, platform-policy, and account risk
- Automation capability and required human time

A high score is not a guarantee. Missing or stale evidence lowers confidence and may block execution.

## Personal payout-route readiness

Country eligibility and platform payout support do not prove that this particular owner can receive funds. The evaluator therefore keeps a separate `payout_route_configured` gate. It must be explicitly true before financial readiness or official-API readiness can pass. The dashboard must never collect wallet secrets or payment credentials; the owner only records whether a usable method is configured. Unknown and false remain blocked.

## Execution safety contract

- No fake clicks/views, ad watching automation, referral abuse, spam, mass account creation, fake identities, fabricated survey answers, CAPTCHA bypass, gameplay bots, or reward manipulation.
- Never store platform passwords, seed phrases, private keys, or payment-card details. Prefer OAuth or official scoped tokens; encrypt secrets at rest and redact logs.
- Do not run arbitrary code supplied by a source or opportunity.
- Each adapter declares allowed domains, API scopes, action types, rate limits, data accessed, and whether human approval is required.
- Financial transfers and withdrawals remain user-confirmed.
- Provide a global stop switch and per-source disable control.

## Delivery phases

### Phase 1 — foundation (implemented in progress)
- Add category and execution-mode enums, evidence/freshness fields, eligibility state, expected effort and payout metadata.
- Add a deterministic evaluator that returns eligibility (eligible, ineligible, unknown), confidence, risk flags, and a transparent ranking breakdown.
- Add tests for unknown eligibility, stale evidence, unsupported automation, and country mismatch.
- Keep all new candidates pending until source review.

### Phase 2 — discovery adapters
- Start with official/public metadata endpoints and curated source registries across all four initial categories.
- Add source-specific rate limits, caching, provenance, and adapter health status.
- Approved RSS/Atom feeds can now be checked automatically on a configurable schedule (default: every 6 hours); the owner can pause or change the interval from the dashboard.
- Feed health is recorded per approved source: last check, last successful check, consecutive failures, and latest error. An owner-only health endpoint classifies feeds as healthy, failing, stale, never checked, or inactive pending review; it performs no additional network requests. It also tracks cumulative check/success counts and a historical success percentage. The dashboard labels the sample as limited until at least five checks; this operational metric is not a guarantee that listings are legitimate or rewards will be paid.
- A SQLite-backed lease prevents overlapping scheduled/manual scans across app workers. Only owner-approved feeds are fetched; newly found items stay in the pending review queue and are never promoted or executed automatically.
- Manual batch discovery remains available. No broad crawling is enabled.

### Competition agent implementation (first vertical slice)
- Added a transparent baseline strategy planner for logic, coding, chess, strategy, and general competitions.
- Added a competition registry contract that accepts only locally registered adapters using an official API, an exact hostname allowlist, and explicit permission for automated agents.
- Added owner-authenticated competition intake, strategy planning, dry-run history, and a guarded submission endpoint.
- The planner now supports the OpenAI Responses API when the server environment contains `AUTOEARN_OPENAI_API_KEY`; `AUTOEARN_OPENAI_MODEL` selects the model (default: `gpt-5.5`). Without that secret, the transparent deterministic baseline is used.
- The API key must be configured only as a server-side secret, never committed to Git or entered in the dashboard. Each strategy-generation request can incur model API charges; the owner initiates it explicitly.
- No platform adapter is installed by default, so real submissions remain unavailable until a platform-specific adapter is reviewed, tested, and explicitly enabled.
- A dry-run never submits an entry or claims a score. Actual participation must use a competition's published rules and official integration.

### Phase 3 — supervised execution
- Introduce task queue, dry-run, explicit capability registry, audit events, user approval gates, retry policy, and kill switch.
- Start with reversible, low-risk actions and official APIs only.

### Phase 4 — earnings reconciliation
- Track estimated, earned, pending, payable, and paid amounts separately.
- Support evidence/receipt records and manual reconciliation before attempting any payout integration.

## Release gates

- Tests must pass in a functioning CI run; a queued or runner-failed workflow is not a pass.
- No automatic execution for unreviewed sources or unknown eligibility.
- No public deployment of review or execution endpoints without authentication, authorization, CSRF protections where relevant, and secret management.
- Never claim guaranteed earnings or verified payouts without evidence.

## Initial focused discovery tracks

The first discovery priorities are game playtesting, puzzle solving, and IQ/reasoning tasks, followed by skill competitions, bug testing, software QA, AI data tasks, microtasks, and freelance projects. The code registry in `autoearn/tracks.py` maps each track to its parent adapter category and conservative execution guidance. Playtesting and software QA remain human-required; skill competitions require an official API and explicit platform permission; AI assistance is conditional on each task's terms. Track priority never overrides country eligibility, payout verification, source review, or the supervision gates above.
