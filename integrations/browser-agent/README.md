# AutoEarn isolated browser game agent

This is a separate Node.js runtime. It is not loaded by the public website and does not receive Supabase credentials.

## Setup

```sh
cd integrations/browser-agent
npm install
npx playwright install chromium
npm test
```

Set `AUTOEARN_GAME_URL` to the starting game-site URL and `AUTOEARN_ALLOWED_ORIGINS` to the exact HTTPS origin reviewed and explicitly approved for automated play.

```sh
AUTOEARN_GAME_URL=https://example-game.invalid/arcade \
AUTOEARN_ALLOWED_ORIGINS=https://example-game.invalid \
npm start
```

The crawler performs a bounded breadth-first walk of same-origin HTTPS links. On pages heuristically classified as folders, it can also expand uniquely named, non-submit buttons whose labels resemble folder/category controls, then re-inspect the page for newly revealed links. It records visited pages, titles, navigation targets, and a preliminary page classification; avoids URL loops; and inspects links found in same-origin iframes. Playwright supports iframe interaction and open Shadow DOM through locators; closed Shadow DOM is not supported. See [Playwright locators](https://playwright.dev/docs/locators), [frames](https://playwright.dev/docs/frames), and [locator ARIA snapshots](https://playwright.dev/docs/api/class-locator).

Configure optional bounds with `AUTOEARN_MAX_PAGES` (default 12, maximum 30), `AUTOEARN_MAX_DEPTH` (default 3, maximum 6), and `AUTOEARN_MAX_DURATION_MS` (default 60 seconds, maximum 5 minutes).

## Page classification

Each visited page is heuristically labeled as `folder`, `game`, `help`, `login`, `verification`, or `unknown`. The result includes a confidence estimate and signal list. It uses title/text, visible navigation labels, and DOM signals such as canvas and score indicators. These are clues, not proof: sites can use custom canvases, misleading labels, or inaccessible controls. A human or a site-specific adapter must validate the classification before play.

## First playable game: 2048

The 2048 strategy now uses a bounded expectimax search: it compares legal moves, models the random appearance of 2 and 4 tiles (90% / 10%), and evaluates empty cells, tile smoothness, monotonicity and keeping the largest tile in a corner. Search depth defaults to 3 and is limited to 1–4 to bound computation. This is a stronger decision strategy than one-step greedy scoring, but it is still a heuristic and does not guarantee a win.

A site-configured Playwright adapter maps visible tile coordinates and values into a 4x4 board. It refuses missing or duplicate coordinates and ambiguous board selectors rather than guessing. The separate runner is deliberately opt-in. Use it only on a game whose official rules allow automation, and configure selectors for that site's actual board markup:

```sh
AUTOEARN_GAME_URL=https://your-approved-game.example/2048 \
AUTOEARN_ALLOWED_ORIGINS=https://your-approved-game.example \
AUTOEARN_AUTOMATION_APPROVED=YES \
AUTOEARN_2048_BOARD_SELECTOR='[data-game-board]' \
AUTOEARN_2048_TILE_SELECTOR='[data-tile]' \
npm run play:2048
```

By default, each rendered tile must expose `data-x`, `data-y`, and `data-value` attributes (zero-based x/y coordinates). For one-based coordinates, set `coordinateBase: 1` when wiring the adapter into a site-specific runner. The runner starts a fresh logged-out browser context, does not import cookies, refuses non-allowlisted origins, stops at verification gates, and limits moves/time. It does not solve arbitrary games. The combined `play:auto` runner also has deterministic browser adapters for tic-tac-toe, Connect Four, and Othello/Reversi when a site exposes the exact documented DOM markers. None of these browser adapters has been validated against a live third-party game site in this development session.

## Run the local AI game agent (experimental)

This runner connects the local Ollama provider to a guarded Playwright keyboard agent. It is experimental: it does not discover a strategy for every game, and an image-capable local model can still misunderstand a board or make poor moves. Use only a game whose published rules explicitly allow automation.

Install a local vision model on the same computer as this runner:

```sh
ollama serve
ollama pull qwen2.5vl:3b
```

Then, in a second terminal:

```sh
cd integrations/browser-agent
npm install
npx playwright install chromium
AUTOEARN_GAME_URL=https://your-approved-game.example/play \
AUTOEARN_ALLOWED_ORIGINS=https://your-approved-game.example \
AUTOEARN_AUTOMATION_APPROVED=YES \
AUTOEARN_LOCAL_MODEL=qwen2.5vl:3b \
npm run play:local-ai
```

Before each decision, a separate local vision pass sends the current JPEG screenshot and a short visible-text excerpt to Ollama at `127.0.0.1:11434`. It returns a bounded structured observation (scene, confidence, game type, objective, state summary, visible text, and visible controls). The runner stops if the model sees a verification gate, cannot identify a game, or reports confidence below 0.65. The decision model then receives that observation plus the screenshot and may choose arrow keys, Enter, Escape, Space, explicitly indexed game-cell clicks, or normalized points inside one site-marked game canvas (`[data-game-board] canvas[data-game-canvas]`). Canvas clicks are refused unless exactly one visible, non-interactive canvas is explicitly marked; arbitrary page coordinates and unmarked canvases are never clicked. A canvas click is added to local owner-feedback memory only after the next observation shows a meaningful state change; its coordinates are reduced to a coarse 10×10 region, and low-confidence clicks are not remembered. This memory stores no screenshots, page text, URLs, or account data. Both perception and decision calls are local and have separate bounded call budgets; configure `AUTOEARN_MAX_STEPS`, `AUTOEARN_MAX_DURATION_MS`, and `AUTOEARN_MAX_MODEL_CALLS` to control runtime. The browser starts logged out, downloads are disabled, popups and off-origin navigation stop the session, and CAPTCHA/verification gates cause a hard stop. It does not submit forms, sign in, buy, deposit, withdraw, claim prizes, or bypass protections.

Ollama inference is local and has no per-request API fee, but downloading model weights and running them requires disk space, RAM/CPU/GPU, and electricity. A 3B vision model may be slow or fail on modest hardware. The provider/runner are not connected to the public website and no model is hosted by AutoEarn.

## Persian rule understanding before play

The experimental local AI runner now performs a separate rule-extraction pass before it starts the action loop. It sends bounded visible page text and an accessibility snapshot to the local Ollama model, asks for a Persian explanation of the objective, controls, turn order, scoring, win/loss conditions, hazards, and unresolved questions, and validates the response against a JSON Schema. The runner refuses to start if the objective or at least one control is missing, confidence is below 0.75, or the page explicitly prohibits automation. A missing statement about automation permission is treated as unclear, never as permission; the operator must still explicitly confirm that the site's published rules allow automated play.

The extractor strips URL query strings/fragments, limits page text, uses a loopback-only Ollama endpoint, and treats all page content as untrusted data rather than instructions to the agent. It also performs a bounded discovery pass over the current page and up to four clearly-labelled, same-origin help/rules links before visual game detection. It does not click arbitrary buttons, submit forms, follow external links, or bypass verification; if no adequate rules are found, it stops rather than inventing them. This is a first safe gate, not proof that a model has understood every game mechanic. The same local model is used for perception and rule extraction; no paid API is called.

## Current stage and boundaries

- **Implemented:** isolated Chromium context; exact HTTPS origin allowlist; bounded same-origin page traversal; duplicate/loop avoidance; visible link/button discovery; limited in-page expansion of folder-like controls; same-origin iframe inspection; heuristic folder/game/help/login/verification classification; limited safe button/link and keyboard adapter actions; and page/depth/time/interaction budgets.
- **Implemented and wired for four explicit DOM game formats:** bounded expectimax for 2048; exact minimax for tic-tac-toe; bounded alpha-beta Connect Four; and bounded Othello/Reversi search. Each turn-based game has a guarded, site-markup-specific browser adapter and move verification.
- **Important live-test limitation:** the runners have passed repository CI and adapter tests, but have not yet been validated against a live third-party game site. Real sites must expose the documented board/cell/column attributes, and the site's official rules must permit automation.
- **Implemented and wired into the experimental local AI runner:** local Ollama visual perception, a separate local decision call, and a private feedback memory that uses only owner-rated actions from matching hashed states. Both providers reject remote endpoints, validate responses, enforce timeouts and call budgets, and use no paid AI API or API key.
- **Not yet implemented:** reliable classification across arbitrary sites, automatic site-specific selector discovery, more game strategies, and robust end-to-end prize/win verification.
- Only use game sites whose official rules explicitly permit automated play.
- CAPTCHA, anti-bot, anti-fraud, access-control, geolocation and payment safeguards are never bypassed. Detection pauses the run for a human.
- No login, signup, form submission, purchases, deposits, withdrawals, prize claims, or personal-data entry are implemented.
- No cookies or browser profile are imported or persisted. This runtime starts logged out.
- The local AI runner uses a vision-capable model such as `qwen2.5vl:3b` for both screenshot perception and action selection. It may still misread a game or make poor moves; low-confidence/unknown screens stop rather than being guessed. This is experimental visual assistance, not reliable universal game understanding or proof of a win.

## Tic-tac-toe browser runner

A deterministic minimax strategy is now connected to an explicit, site-configured DOM adapter. The adapter requires exactly nine cells with unique `data-index="0"` through `data-index="8"` attributes and readable marks via `data-mark` (or cell text). It clicks only the selected empty cell, checks that the configured player is actually next, and verifies that the intended mark appeared after the click. This is not a universal visual detector; a site-specific selector and mark mapping are required.

Use only on sites whose published rules explicitly permit automated play:

```sh
AUTOEARN_GAME_URL=https://your-approved-game.example/tic-tac-toe \
AUTOEARN_ALLOWED_ORIGINS=https://your-approved-game.example \
AUTOEARN_AUTOMATION_APPROVED=YES \
AUTOEARN_TTT_BOARD_SELECTOR='[data-game-board]' \
AUTOEARN_TTT_CELL_SELECTOR='[data-index]' \
AUTOEARN_TTT_PLAYER=X \
npm run play:tic-tac-toe
```

Set `AUTOEARN_TTT_PLAYER` to the mark assigned to the agent on that site. The runner starts logged out, uses a fresh browser context, checks the exact HTTPS origin, stops at verification gates, and has a maximum of nine moves. It does not sign in, submit forms, make purchases, or claim prizes. No live third-party site test has been performed yet.

The tic-tac-toe adapter now labels its normalized observation as `tic-tac-toe` for registry dispatch. When it is the opponent's turn, the strategy emits a bounded `wait-for-turn` action (up to 30 seconds); the adapter polls the board and verifies that the agent's turn has arrived before another move. Waiting is counted against the runner's step/time budgets, and a timeout stops the run rather than guessing or clicking.

## Conservative game-type detection

The site crawler now reports a separate `gameDetection` result for each visited page. It recognizes only explicit, unambiguous board signatures inside elements marked `data-game-board`:
- Tic-tac-toe: exactly nine descendants with unique `data-index="0..8"` and readable `data-mark`/text values limited to X, O, or empty.
- 2048: descendants with explicit `data-x`, `data-y`, and `data-value` attributes describing unique 4×4 coordinates and power-of-two tile values.
- Connect Four: exactly 42 uniquely indexed `data-game-cell` descendants with X/O/empty marks; the playable adapter additionally requires seven explicit indexed `data-game-column` controls.
- Othello/Reversi: exactly 64 uniquely indexed `data-game-cell` descendants with B/W/empty marks and an explicit `data-current-player` value.

Text such as “2048”, “score”, or “play game” is never enough to identify a playable game. Multiple or malformed candidates return no game type. Detection is metadata only: it does not automatically click or play. The matching site's selectors and player configuration still need to be reviewed before using a dedicated adapter; arbitrary canvas-only boards and games without these explicit attributes remain unsupported.

## Automatic selection between supported games

A guarded combined runner is available as `npm run play:auto`. It traverses a bounded set of same-origin game/folder links, then selects exactly one supported board. It can dispatch to the 2048, tic-tac-toe, or Connect Four adapter. Set `AUTOEARN_TTT_PLAYER=X|O` or `AUTOEARN_CONNECT_FOUR_PLAYER=X|O` for turn-based games; 2048 selects its expectimax strategy automatically.

```sh
AUTOEARN_GAME_URL=https://your-approved-game.example/play \
AUTOEARN_ALLOWED_ORIGINS=https://your-approved-game.example \
AUTOEARN_AUTOMATION_APPROVED=YES \
AUTOEARN_TTT_PLAYER=X \
npm run play:auto
```

The board must expose the documented `data-game-board` marker and the explicit attributes required by its adapter. Connect Four additionally needs the column-control markers documented below. If no single valid board is found, or more than one candidate is present, the runner stops instead of guessing. This is automatic game/strategy selection for four known DOM formats, not general visual recognition of arbitrary games. It uses a fresh logged-out context, exact HTTPS origin allowlisting, no downloads, and bounded moves/time; verification gates and unexpected popups/origin changes stop execution.


## Local visual game-state perception

The experimental `play:local-ai` runner now performs two local model stages for each observation:

1. **Perception:** `ollama-game-perception.mjs` receives a JPEG screenshot and bounded visible text, then returns a validated JSON summary of scene type, confidence, game type, objective, state summary, visible text, and visible controls.
2. **Decision:** `ollama-decision-provider.mjs` receives the structured observation and screenshot, then returns one allowlisted keyboard action or stop.

The runner refuses to continue when perception identifies a verification page, cannot confidently identify a playable game, or reports confidence below 0.65. This makes the agent more cautious and gives the decision model a structured state description, but the model can still hallucinate; the confidence value is self-reported, not independently calibrated. There is no guarantee of winning or earning rewards. All inference stays on the same machine through the loopback Ollama endpoint; no paid hosted API is called.


## Private local experience memory and feedback

The experimental local AI runner keeps a small local-only experience ledger at `.autoearn/experience-memory.json` (ignored by Git). It stores only a random experience ID, game type, a SHA-256 hash of the short perceived state summary/objective, an allowlisted keyboard key, and whether the owner later rated the move good or bad. It does **not** save screenshots, raw page text, URLs, cookies, account data, or credentials.

After a verified move, the runner prints pending experience IDs in its final report. A verified page change is not treated as a win or as a good move. To teach the agent, rate an experience explicitly:

```sh
npm run feedback -- <experience-id> good
npm run feedback -- <experience-id> bad
```

The next time the same game type and same normalized state summary appear, the local decision prompt receives a short list of owner-rated actions for that exact state. These hints are advisory, not guaranteed strategies; the model still evaluates the current screenshot. Unrated experiences are never used as positive or negative examples. The memory is local to the computer running the agent and can be removed by deleting `.autoearn/experience-memory.json`.

Set `AUTOEARN_MEMORY_FILE` to choose a different local file path. Do not place this file in a public repository or shared folder.


## Bounded instruction-page discovery

Before visual game-state detection, `play:local-ai` reads the current page and may visit up to four clearly-labelled same-origin HTTPS help, rules, guide, tutorial, or instructions links (five pages total including the starting page). It collects bounded visible text and same-origin iframe text, strips query strings/fragments from discovered links, then returns to the original game URL before play. It never clicks arbitrary page controls or follows external links. CAPTCHA/verification text or an origin change stops the run. This helps when instructions live on a separate help page, but it does not automatically navigate folder widgets or start a game from a help-only landing page.


## Nested game/folder discovery

The conservative `play:auto` runner can inspect the starting page and up to seven additional same-origin HTTPS pages (maximum depth two), following only links whose visible label/path clearly indicates games, puzzles, arcade, levels, folders, or categories, or which carry explicit `data-game-link` / `data-game-folder` markers. It recognizes only the four implemented explicit board signatures: 2048, tic-tac-toe, Connect Four, and Othello/Reversi. If it finds exactly one supported board, it navigates to that board and runs the matching strategy; if it finds none or multiple candidates, it stops rather than guessing. Account/payment/security paths, external origins, verification gates, arbitrary buttons, forms, and login flows are not followed. This is bounded discovery, not a universal website crawler.


## Guarded mouse selection for explicitly marked game cells

The experimental local AI runner supports a narrow mouse action: `click-cell` with an index from 0 to 99. It is enabled only when exactly one `[data-game-board]` exists and the target is a unique visible `[data-game-cell][data-game-cell-index="N"]` descendant. The target and its ancestors must not be links, buttons, form controls, or role=button/link elements. Arbitrary screen coordinates, selectors, page buttons, links, menus, and form controls are never sent to Playwright. Observations include available safe cell indices and short labels. This requires site markup to expose explicit data attributes; canvas-only or unmarked mouse games remain unsupported. The rule extractor accepts game-cell/tile/square click descriptions, not generic page clicks.


## Conservative win/loss state reporting

The local AI runner now checks explicit `data-game-outcome` and `data-game-status` markers before using clear visible win/loss phrases. Explicit active-state markers override incidental text elsewhere on the page. Unknown states remain unknown; a page change or a higher score is not counted as a win. This reports a game's visible/DOM terminal state only and does not prove a cash reward, prize eligibility, or withdrawable income.


## Connect Four browser runner (explicit column controls required)

The combined `npm run play:auto` runner now recognizes a Connect Four board only when a single `[data-game-board]` contains exactly 42 uniquely indexed `[data-game-cell][data-game-cell-index]` cells with readable X/O/empty marks. It also requires seven explicit, uniquely indexed `[data-game-column][data-game-column-index="0..6"]` column controls; the agent clicks a column control, never an arbitrary screen coordinate or guessed cell. The adapter validates gravity and turn counts, waits for the configured player's turn, and verifies that exactly one token appeared in the expected landing cell.

Set `AUTOEARN_CONNECT_FOUR_PLAYER=X` or `O` when the site assigns the agent a mark. The same opt-in and exact HTTPS origin checks apply, and the site's published rules must explicitly permit automation. If the board does not expose these exact semantics, the runner refuses to play. This strategy uses bounded depth-4 minimax with alpha-beta pruning and tactical win/block checks; it is a heuristic, not a guarantee of winning. No live third-party Connect Four site has been tested.

```sh
AUTOEARN_GAME_URL=https://your-approved-game.example/connect-four \\
AUTOEARN_ALLOWED_ORIGINS=https://your-approved-game.example \\
AUTOEARN_AUTOMATION_APPROVED=YES \\
AUTOEARN_CONNECT_FOUR_PLAYER=X \\
npm run play:auto
```


## Othello browser runner

The combined `npm run play:auto` runner also supports Othello/Reversi when the page exposes exactly 64 indexed `[data-game-cell][data-game-cell-index]` cells inside one `[data-game-board]` and an explicit `data-current-player="B|W"` (or BLACK/WHITE) attribute. Cells must expose B/W or BLACK/WHITE marks (X/O is accepted as a documented alias). The strategy computes legal captures and uses a bounded depth-3 search with corner, mobility, edge, and disc-count evaluation. It verifies the complete expected board after each placement.

Set `AUTOEARN_OTHELLO_PLAYER=B` or `W`. If the configured side has no legal move, the agent only passes when the page exposes one unique visible `[data-game-pass]` control; otherwise it stops rather than guessing. If neither side can move, the game is reported as finished. The site's published rules must explicitly permit automation, and all normal origin/verification/time limits still apply. No live third-party Othello site has been tested.


## Explicit expandable game folders

Game discovery can now inspect a site's explicitly marked expandable folder buttons. It activates only visible, enabled `button[data-game-folder-toggle]` elements whose type is `button` and which are not inside a form; it never clicks generic buttons, links, or unlabeled page controls to guess where a game might be. Each toggle is opened only long enough to read newly revealed same-origin game links, then collapsed again. The discovery pass is limited to eight such controls per page and still obeys the existing page/depth/time budgets. If a toggle navigates away from the approved HTTPS origin or cannot be safely collapsed, discovery stops. Sites that do not mark folder toggles explicitly remain unsupported by this path.


### Canvas-only rule handling
The local rule extractor accepts canvas-only controls only when the browser confirms exactly one visible, explicitly marked game canvas ([data-game-board] canvas[data-game-canvas]). That verified fact is passed to the local rules model. Generic mouse controls, menus, and unmarked canvases remain unsupported. This compatibility gate does not prove that the visual model can reliably identify every game's hit target.


Canvas click decisions also require the local model to report confidence of at least 0.8. The decision parser and the browser adapter both enforce this threshold; it is a conservative self-reported confidence gate, not a calibrated probability or guarantee of a correct move.


## Canvas motion estimation (experimental)

The local visual pass can now return up to 30 bounded object boxes (player, target, hazard, goal, obstacle, or other). The runner maps those full-viewport boxes into the explicitly marked game canvas, then tracks same-role/same-label detections between observations. For matched objects it estimates normalized velocity and extrapolates a short 500 ms position; only high-confidence hazards and obstacles are forwarded as predicted hazard regions to the decision prompt. Stale observations are not extrapolated, boxes are clipped to the canvas, and the model is instructed to treat predictions as uncertain clues rather than guaranteed trajectories.

This is deliberately a lightweight constant-velocity estimate, not physics simulation or pathfinding. It can fail when objects change appearance, overlap, teleport, accelerate, or are detected inconsistently. The agent must still stop if the next action is unclear; no claim of safe navigation or improved win rate is made until tested on an approved real game.


The motion tracker also labels short observed patterns as horizontal, vertical, diagonal, stationary, or oscillating when enough consecutive matches exist. A high-confidence player detection allows a basic approaching-player flag when a hazard's observed distance decreases. These are descriptive heuristics only: no collision prediction, path guarantee, or automatic win claim is implied.



## Adaptive session feedback and conservative outcome rating

The local runner now carries at most five recent verified action outcomes into the next decision prompt. Each entry is reduced to an allowlisted action key, a good/bad/neutral progress suggestion, bounded confidence, and a few short signal labels. This is session-local advisory context, not automatic model training. Geometric progress estimates are not treated as ground truth, and neutral observations are not counted as failures.

Automatic positive/negative experience rating is restricted to a changed outcome explicitly read from a site's `data-game-outcome` or `data-game-status` attribute. Visible-text phrases such as “you win” remain lower-confidence hints and cannot automatically rate memory. Owner review remains the preferred source of strategy feedback.

Local memory now discards records older than 30 days when it loads, in addition to its 1,000-record cap. This limits stale strategy hints; it does not change the local-only storage or privacy boundaries above.


## Repeated-state loop watchdog

The generic game loop can now accept a compact semantic state key from a site adapter. If the same board state is observed three times in one run, the agent stops with `stalled / repeated_state` rather than repeatedly issuing moves into a cycle. The local visual runner builds this key from the perceived game type, short state summary, objective, and rounded high-confidence object geometry. This is a conservative loop guard: a legitimate game may revisit a board state, so the stop is a request for review, not a claim that no winning strategy exists. The watchdog is bounded and does not alter the step/time budgets.


The local decision prompt also receives the last six sanitized actions from the current run (keyboard key, bounded cell index, or coarse canvas bucket). It can use this short sequence to avoid repeating moves without considering their effects. A successful verification means the board changed; it does not mean the move was strategically good. The action history is in-memory for the current run and is not added to the persistent experience ledger.
\n\n### Paired 2048 strategy evaluation\n\n`simulate2048Episodes()` now evaluates every configured search depth on the exact same deterministic episode seeds and reports paired score wins/ties/losses, average and median paired score deltas, and the paired average maximum-tile delta against the first configured depth. It also reports a deterministic 1,000-resample percentile bootstrap interval for the mean paired score difference. The interval is descriptive and can be very wide or unstable with a small episode count; use more seeds/episodes before drawing conclusions. This remains a synthetic local simulator, not a live-site win-rate estimate or evidence of earnings.\n

## Reproducible 2048 heuristic-weight experiment

Run the paired local comparison with 20 episodes per variant by default (40 simulated games total), using the same deterministic seed list and search depth for the classic heuristic and the snake-weight candidate:

```sh
node games/run-2048-heuristic-comparison.mjs
```

Optional bounded settings are `AUTOEARN_2048_SEED` (0..4294967295, default 2048), `AUTOEARN_2048_EPISODES` (2..20, default 20), `AUTOEARN_2048_DEPTH` (1..3, default 2), `AUTOEARN_2048_MAX_MOVES` (1..1000, default 500), and `AUTOEARN_2048_SNAKE_WEIGHT` (0..2, default 1). The JSON report includes paired score and maximum-tile outcomes, 2048 completions, move-limit stops, and a deterministic bootstrap interval. This is a local synthetic benchmark only; it does not establish real-site win rates, reward eligibility, or earnings.

### Current 2048 heuristic tuning result

A seeded paired CI experiment (20 episodes per variant, depth 2, up to 500 moves, seed 2048) compared the no-snake baseline against snake weights 0.25, 0.5, and 1. The baseline averaged 7,910 points. Candidate averages were 7,648.8, 7,677.4, and 7,591.4 respectively; none reached 2048 within the move limit. The 0.25 candidate's bootstrap 95% interval for score delta was entirely below zero (-565.645 to -16.73), while intervals for 0.5 and 1 crossed zero. Accordingly, the default snake bonus is disabled; the experimental feature remains available through an explicit weight. These small synthetic episodes are tuning evidence only, not proof of real-site performance or earnings.


## 2048 search-policy experiment

CI runs a reproducible, bounded comparison of fixed expectimax depths 1, 2 and 3 against the adaptive policy (8 seeded episodes, 250 moves per episode). The first recorded run produced:

| Policy | Average score | Average highest tile | Search nodes visited |
| --- | ---: | ---: | ---: |
| Fixed depth 1 | 3,119.5 | 256 | 0 |
| Fixed depth 2 | 3,237 | 256 | 127,522 |
| Fixed depth 3 | 3,423.5 | 320 | 3,454,925 |
| Adaptive | 3,231.5 | 256 | 285,645 |

In paired comparisons, adaptive averaged 5.5 fewer points than fixed depth 2 and used more search nodes in this small run; against fixed depth 3 it averaged 192 fewer points while visiting about 396,160 fewer nodes per episode. Adaptive beat fixed depth 1 by 112 average points. No policy reached 2048, and all episodes stopped at the 250-move cap. This is a small synthetic benchmark, not a reliable win-rate estimate or evidence of real-site earnings. Do not treat adaptive as universally best; more seeds, longer episodes and live-site rules-compliant validation are still needed.
