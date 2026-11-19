# AutoEarn AI

A private, owner-only opportunity discovery and reward-tracking workspace.

The web interface connects directly to Supabase Auth and the three owner-protected tables. The browser uses only the project's publishable key; Row Level Security remains the database authorization boundary. It does not promise income or automate clicks, gameplay, ad views, referrals, spam, account creation, or platform activity. The guided-session button only opens the official HTTPS page in a new tab and records that the owner started a session.

## Current implementation

- Supabase email/password sign-in (no public registration UI).
- Supabase-backed opportunities, tasks, and rewards.
- Owner ID is attached to every inserted record; database RLS validates ownership.
- Owner-started guided sessions open the official HTTPS page and are recorded as approved tasks; third-party gameplay remains manual.
- Local 3×3 sliding-puzzle lab demonstrates automatic solving on a self-contained demo board; it has no rewards, external accounts, or platform interaction.
- No automatic login, signup, personal-data submission, purchases, deposits, or gameplay. Any future platform-specific assistance must respect the platform terms and request consent before sensitive actions.
- Human approval is required before a task can be marked completed.
- Explainable opportunity metadata score; not a guarantee of legitimacy or payment.
- The FastAPI host serves the static app and a health endpoint only; no unauthenticated SQLite CRUD API is exposed. User data is stored in Supabase.

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

## Opportunity eligibility gate

Guided sessions are available only after the owner reviews the official terms URL and confirms country eligibility, a specific, officially supported payout method (wallet, bank transfer, or bank card), no required deposit or purchase, and explicit permission for automated gameplay. This is an owner attestation, not an independent verification by AutoEarn; do not mark an opportunity eligible unless every item is confirmed from official sources. Guided sessions still open the platform for manual participation only.

## Autonomous game-agent engine

- Indexed cell clicks are now checked twice: the local model may choose only an index exposed in the current observation's safe click-target list, and the browser adapter revalidates the target before clicking. A model response that invents an index is rejected and the action is not executed.

- `static/game-agent.js` provides an observe → decide → act → verify loop for game adapters.
- Each adapter exposes only its own game state and bounded actions. Runs have explicit action allowlists, step/time budgets, cancellation, event reporting and post-action verification.
- Failed verification stops the run. AI decisions will use local/open-weight models or deterministic game strategies only; no paid hosted AI API, API key, or per-call billing is required.
- Third-party game adapters remain disabled until official rules explicitly permit automation. CAPTCHA, anti-bot, access-control and payment safeguards are never bypassed.
- The built-in sliding-puzzle demo now runs through the same bounded agent loop and verifies each move before reporting completion.

### Observable game-progress feedback (experimental)

The local browser agent can attach a conservative progress assessment to a verified action. It uses only high-confidence visible player/target boxes, predicted hazard overlap, and explicit terminal outcome markers. It labels a step good, bad, or neutral as a review suggestion; neutral is the default when evidence is missing. The evaluator also accepts score, level, lives and mistake counters only when both observations explicitly mark their source as a DOM attribute; untrusted visual/text estimates are ignored. This metric path is an evaluator capability and is not automatically populated by every game adapter. These suggestions are not automatically promoted into owner ratings or model training, and visual geometry can be wrong. No win-rate or earnings guarantee is made.

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
