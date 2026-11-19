# AutoEarn AI

A private, owner-only opportunity discovery and reward-tracking workspace.

The web interface connects directly to Supabase Auth and the three owner-protected tables. The browser uses only the project's publishable key; Row Level Security remains the database authorization boundary. It does not promise income or automate clicks, gameplay, ad views, referrals, spam, account creation, or platform activity. The guided-session button only opens the official HTTPS page in a new tab and records that the owner started a session.

## Current implementation

- Supabase email/password sign-in (no public registration UI).
- Supabase-backed opportunities, tasks, and rewards.
- Owner ID is attached to every inserted record; database RLS validates ownership.
- Guided sessions are fail-closed and currently disabled: owner-entered checklists and valid HTTPS links are not independent verification. Re-enable only after a trusted server-side verifier can establish official terms, payout, geography, and platform automation permission. Third-party activity remains manual.
- Local 3×3 sliding-puzzle lab demonstrates automatic solving on a self-contained demo board; it has no rewards, external accounts, or platform interaction.
- No automatic login, signup, personal-data submission, purchases, deposits, or gameplay. Any future platform-specific assistance must respect the platform terms and request consent before sensitive actions.
- Human approval is required before a task can be marked completed.
- Discovery search snippets and owner checklists are unverified leads, not proof of official status, cash payout, geographic eligibility, or permission to automate. A clean heuristic result never establishes legitimacy.
- Explainable opportunity metadata score; not a guarantee of legitimacy or payment.
- The FastAPI host serves the static app and a health endpoint only; no unauthenticated SQLite CRUD API is exposed. User data is stored in Supabase.

## Reward ledger and monthly reporting

The owner-only reward ledger validates positive amounts, three-letter currency codes, and known statuses. A reward marked paid must include a transaction reference or other payment evidence. Dashboard totals keep currencies separate and distinguish paid (with a reference), confirmed, and pending amounts. Monthly history groups records by their UTC creation month and currency, showing the same status breakdown for the six most recent months with valid dates. These are manually entered records, not bank verification or proof of withdrawal; rejected records are not included in the three displayed totals.


Completed guided sessions now include a **Record actual reward** action linked to that opportunity. It preselects the opportunity in the reward form and defaults the status to pending; the owner must enter the actual amount and currency. This is a convenience link only: completing a session does not create or imply a reward, and paid status still requires a transaction reference.

## Supabase setup

1. In Supabase Dashboard, open **Authentication → Sign In / Providers** and turn off **Allow new users to sign up**. This makes the project invite-only; existing users can still sign in.
2. Open **Authentication → Users** and create/invite only your own email address.
3. Open **Project Settings → API Keys** and copy the **publishable** key (starts with `sb_publishable_`). Never copy a secret or service_role key into the website.
4. Put that publishable key in `static/config.js` as the value of `publishableKey`.
5. Deploy the static `static/` directory to a static host over HTTPS. Configure the host to serve `index.html` at the site root.

The Supabase project URL is already configured in `static/config.js`. No database password or service-role key is required in the browser.

## Development

Requires Python 3.10 or newer.

```bash
pip install -r requirements.txt
pytest -q
```

## Security

The `opportunities`, `tasks`, and `rewards` tables have Row Level Security policies that scope rows to `auth.uid()`. Do not weaken or disable these policies. A publishable key is not an authorization mechanism by itself; the authenticated user JWT and RLS policies control access.

## Scope and risk

Scores use only metadata entered by the owner. They are not proof that a platform is legitimate or that a reward will be paid. Verify eligibility, country restrictions, withdrawal thresholds, and platform terms before participating. Website discovery and analysis must respect site terms, robots policies, privacy, and applicable law.

## Discovery due-diligence signals

Automatically discovered candidates remain unverified and are saved for owner review. The discovery pipeline records text-based review alerts when a search result mentions identity/KYC checks or geographic restrictions, or when it does not disclose a minimum withdrawal, a specific payout method, withdrawal-fee terms, a prize amount (the amount must be textually associated with a prize/reward label, so a withdrawal threshold alone does not count), payout timing, organizer identity, or winner-selection method. These alerts are prompts to inspect the official terms, not findings that a site definitely requires KYC, excludes a particular country, or charges fees. Country restrictions are surfaced for review and are not used to filter discovery results. A clean alert list is not proof of legitimacy, official domain ownership, eligibility, or payment. Opportunity cards also show a 0–100 evidence-completeness heuristic: it deducts points for missing minimum-withdrawal details (12), payout method (10), withdrawal fees (8), prize amount (15), payout timing (10), organizer identity (20), winner-selection method (8), and an official terms link (10). KYC and geographic-restriction mentions are displayed as review alerts but are not scored as inherently negative. This text-only index measures disclosure completeness, not trustworthiness, country eligibility, actual cash-out success, or permission to automate. The opportunities list can be sorted by highest/lowest evidence completeness or newest first; candidates without a discovery evidence record sort after scored candidates. Sorting is advisory and never changes eligibility status or authorizes an action. The filtered list also displays a comparison summary with total/scored candidates, average evidence completeness, and high (80–100), medium (50–79), low (0–49), and unscored counts. The average excludes unscored manual entries and is not a success-rate statistic.

## Opportunity eligibility gate

Guided sessions are blocked for discovered, reviewing, ineligible, and archived opportunities. They can start only when an opportunity has the explicit `eligible` status, which must be reserved for opportunities whose official terms, country eligibility, specific supported cash-out method, no-deposit/no-purchase entry, minimum age, KYC requirements, and platform rules have been independently checked. The owner checklist is an attestation and does not itself grant `eligible` status. At runtime, the guided-session guard also requires a parseable latest review record, known minimum withdrawal/fees/minimum age, confirmed country and free entry, a supported payment method, a known KYC answer, explicit automation permission, and valid public HTTPS terms, payout, and automation evidence URLs. Setting the database status to `eligible` alone is insufficient. Guided sessions only open the public HTTPS page for manual participation; they do not sign up, log in, submit information, spend money, or automate gameplay. If official rules do not clearly permit automation, automated gameplay remains disabled.

## Autonomous game-agent engine

- Indexed cell clicks are now checked twice: the local model may choose only an index exposed in the current observation's safe click-target list, and the browser adapter revalidates the target before clicking. A model response that invents an index is rejected and the action is not executed.

- `static/game-agent.js` provides an observe → decide → act → verify loop for game adapters.
- Each adapter exposes only its own game state and bounded actions. Runs have explicit action allowlists, step/time budgets, cancellation, event reporting and post-action verification.
- Failed verification stops the run. AI decisions will use local/open-weight models or deterministic game strategies only; no paid hosted AI API, API key, or per-call billing is required.
- Third-party game adapters remain disabled until official rules explicitly permit automation. CAPTCHA, anti-bot, access-control and payment safeguards are never bypassed.
- The built-in sliding-puzzle demo now runs through the same bounded agent loop and verifies each move before reporting completion.

### Observable game-progress feedback (experimental)

The local browser agent can attach a conservative progress assessment to a verified action. It uses only high-confidence visible player/target boxes, predicted hazard overlap, and explicit terminal outcome markers. It labels a step good, bad, or neutral as a review suggestion; neutral is the default when evidence is missing. The evaluator also accepts score, level, lives and mistake counters only when both observations explicitly mark their source as a DOM attribute; untrusted visual/text estimates are ignored. This metric path is an evaluator capability and is not automatically populated by every game adapter. These suggestions are not automatically promoted into owner ratings or model training, and visual geometry can be wrong. No win-rate or earnings guarantee is made.

### Conservative experience-hint learning

The local experience ledger stores only hashed game-state summaries and allowlisted actions, not screenshots, page text, URLs, credentials, or cookies. An action is not surfaced as a learned hint until it has at least two rated samples for the exact game state; the success rate uses Laplace smoothing. Before passing hints to Ollama, the decision provider validates and bounds their fields, labels them positive, negative, or uncertain, and tells the model to treat them only as advisory evidence. Negative patterns are cautions, not hard bans; current rules, hazards, and observations always take precedence. Two samples are a minimum evidence filter, not statistical proof of a strategy.

### Authoritative terminal-outcome feedback

When a game adapter exposes a new, explicit `won` or `lost` outcome from a DOM attribute, the evaluator now returns that terminal result immediately. Lower-confidence geometry, hazard, or score signals cannot contradict a confirmed terminal outcome or reverse its owner-feedback label. Visible-text hints and non-terminal progress continue through the conservative heuristic path. This precedence applies only to explicitly sourced DOM terminal markers.

### Trusted score and state metrics

The local Playwright observer reads `data-game-score`, `data-game-level`, `data-game-lives`, and `data-game-mistakes` only from exactly one explicitly marked `[data-game-board]`. Values must be non-negative integers. These attributes are merged into the game observation with `metricsSource: "dom-attribute"`; absent, malformed, ambiguous, or unmarked values are ignored. Progress feedback can then compare successive observations. The observer does not infer these values from page text or screenshots.

### Reproducible 2048 strategy benchmark (experimental)

Run `node integrations/browser-agent/games/run-2048-benchmark.mjs` to compare expectimax depths 1–3 over 12 seeded synthetic boards. The report includes immediate heuristic mean/median, legal-decision counts, and selected directions. Use `create2048BenchmarkBoards` and `benchmark2048Strategies` from `2048-strategy-benchmark.mjs` to provide a fixed seed, board count, occupancy, or custom positions. This is a deterministic strategy-regression aid—not a measured win rate, a real website test, or evidence of earnings. Keep third-party automation disabled unless the game's official rules explicitly allow it.


### Full-episode 2048 simulation (experimental)

Run `node integrations/browser-agent/games/run-2048-episodes.mjs` to simulate complete games with seeded tile spawns and compare expectimax depths 1–3. The report includes score, median score, highest tile, games reaching 2048, game-over count, move-limit stops, and move counts. Defaults are 5 episodes per depth with a 500-move cap; the simulator accepts bounded custom settings through `simulate2048Episodes`. Results are reproducible local simulations, not real-site win rates or a promise of winning or earning money.


### Adaptive 2048 search depth (experimental)

The dedicated 2048 browser runner now chooses expectimax depth from board occupancy: depth 1 with 10–16 empty cells, depth 2 with 6–9 empty cells, and depth 3 with 0–5 empty cells. This is a bounded compute heuristic intended to spend more lookahead on crowded boards, not a proven optimal policy. The fixed-depth `create2048Decision` remains available for controlled comparisons; `createAdaptive2048Decision` is used by `play-2048.mjs`.

### Paired 2048 policy comparison (experimental)

Run `node integrations/browser-agent/games/run-2048-policy-comparison.mjs` to compare fixed depths 1–3 with the adaptive policy on the same deterministic episode seeds. The report includes paired score, maximum-tile, search-node, cache-hit, and budget-exhaustion differences for every policy against each fixed-depth baseline, score and tile win/tie/loss counts, the minimum/maximum and average absolute paired score differences (to expose episode-to-episode spread), move-limit stops, and the adaptive policy's depth-use counts. The spread is descriptive only; small episode counts do not support strong statistical conclusions. Identical seeds provide a reproducible paired experiment, but different board trajectories mean this remains synthetic evidence—not a real-site win rate or earnings claim.

### Bounded 2048 search budget (experimental)

Each expectimax decision now has a hard default cap of 25,000 expanded search nodes (configurable from 1 to 200,000). The allowance is divided evenly among legal root moves, so an early direction cannot consume the whole budget before later directions are evaluated. If the cap is reached, remaining branches fall back to the board heuristic; if the allowance is smaller than the number of legal moves, all root choices are evaluated heuristically without exceeding the cap. Decisions expose visited-node, cache-hit, per-move budget, per-direction search, and budget-exhaustion diagnostics; paired policy simulations aggregate these to compare search cost as well as scores. The cap bounds search expansion, not total browser runtime, and a budget-limited move may be less informed than a complete search.

### Paired 2048 heuristic comparison (experimental)

Run `node integrations/browser-agent/games/run-2048-heuristic-comparison.mjs` to compare the classic heuristic (snake weight 0) with the current snake-ordering heuristic (snake weight 1). Both variants use identical deterministic episode seeds, the same expectimax depth, and the same move cap. The report includes average/median score, average maximum tile, 2048 completions, game overs, paired score wins/ties/losses, average paired score and tile deltas, and a deterministic 1,000-resample bootstrap interval. This isolates the snake bonus while retaining the same other evaluation terms. It is synthetic local evidence only—not a live-site win rate, guarantee, or earnings claim.

### Paired 2048 heuristic-weight experiment (experimental)

Run `node integrations/browser-agent/games/run-2048-heuristic-comparison.mjs` to compare the classic evaluation (snake weight 0) against the current snake-position term (weight 1). Both variants use the same deterministic episode seeds, expectimax depth, and move limit. The report includes per-variant score/tile/outcome summaries and paired score deltas with a deterministic bootstrap interval. The runner currently defaults to 10 paired episodes at depth 2. These are synthetic local-game measurements only; do not interpret them as third-party win rates or expected earnings.


### Opportunity discovery provenance

Newly discovered opportunity records include a bounded provenance marker in their notes: the search provider, exact search query, discovery timestamp, and a short excerpt returned by the search provider. The dashboard displays the source, timestamp, query, and escaped excerpt so an owner can trace why a candidate was surfaced. This is search-result provenance only: it does not verify the destination's identity, official rules, cash payout, country eligibility, or payment history. Verify those independently from the platform's official pages before changing an opportunity's eligibility status.

### Duplicate discovery handling

Within one search batch, tracking-only URL differences are canonicalized and merged. Distinct search queries, excerpts, reward descriptions, categories, and review notes are retained in the merged candidate. Discovery diagnostics distinguish duplicates collapsed within the current batch from candidates already saved by the owner. Existing owner records are intentionally left unchanged when rediscovered: status, score, official review notes, and other manual decisions are not overwritten by fresh search snippets.

### Fail-closed free-cash eligibility review

The Python opportunity module now exposes `EligibilityReview` and `evaluate_eligibility`. A candidate remains blocked unless the owner confirms all five items from official information: terms reviewed, country eligibility, a supported cash payout, no required deposit or purchase, and platform rules reviewed. The result lists each confirmation still missing. Passing this checklist permits manual review only; it never enables automated gameplay or proves that a platform will pay. Automated interaction remains disabled unless separately authorized by the platform's official rules and the applicable safety checks. Unknown or placeholder entries such as “Not stated”, “Unknown”, or “TBD” do not satisfy required withdrawal, fee, or minimum-age details. An incomplete review stays in `reviewing`; `ineligible` is reserved for explicit official disqualifiers such as unsupported payout, country exclusion, or paid/deposit-required entry. If automation is prohibited or unclear, the opportunity is not marked ineligible solely for that reason, but automated play remains disabled and any manual use must still follow the platform's rules.
