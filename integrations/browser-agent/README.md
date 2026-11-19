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

By default, each rendered tile must expose `data-x`, `data-y`, and `data-value` attributes (zero-based x/y coordinates). For one-based coordinates, set `coordinateBase: 1` when wiring the adapter into a site-specific runner. The runner starts a fresh logged-out browser context, does not import cookies, refuses non-allowlisted origins, stops at verification gates, and limits moves/time. It does not solve arbitrary games; only the 2048 adapter is currently wired to an autonomous decision strategy. The browser runner has not been executed against a real game site in this development session.

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

The runner sends screenshots and a bounded text snapshot to Ollama at `127.0.0.1:11434` only. The model may choose only arrow keys, Enter, Escape, or Space. The browser starts logged out, downloads are disabled, popups and off-origin navigation stop the session, and CAPTCHA/verification gates cause a hard stop. It does not submit forms, sign in, buy, deposit, withdraw, claim prizes, or bypass protections. Configure `AUTOEARN_MAX_STEPS`, `AUTOEARN_MAX_DURATION_MS`, and `AUTOEARN_MAX_MODEL_CALLS` to lower or raise bounded run limits (within the hard caps in code).

Ollama inference is local and has no per-request API fee, but downloading model weights and running them requires disk space, RAM/CPU/GPU, and electricity. A 3B vision model may be slow or fail on modest hardware. The provider/runner are not connected to the public website and no model is hosted by AutoEarn.

## Current stage and boundaries

- **Implemented:** isolated Chromium context; exact HTTPS origin allowlist; bounded same-origin page traversal; duplicate/loop avoidance; visible link/button discovery; limited in-page expansion of folder-like controls; same-origin iframe inspection; heuristic folder/game/help/login/verification classification; limited safe button/link and keyboard adapter actions; and page/depth/time/interaction budgets.
- **Implemented for one wired game:** bounded expectimax 2048 strategy, a defensive configurable DOM-to-board adapter, and a separate guarded runner that can execute and verify arrow-key moves when the site's board selectors are configured. The 2048 runner has not yet been tested against a live third-party game site.\n- **Implemented as a tested strategy module:** exact minimax for tic-tac-toe, plus a strategy registry that accepts normalized game state. It is not yet connected to screenshot/DOM recognition or a browser click adapter, so it does not autonomously play tic-tac-toe on websites yet.
- **Implemented but not yet wired into a game runner:** an optional local-only Ollama decision provider. It sends bounded observations and optional screenshots only to a loopback service (`localhost`); remote endpoints are rejected. It has an action allowlist, timeout, and per-instance call budget. No paid AI API or API key is used.
- **Not yet implemented:** reliable classification across arbitrary sites, automatic site-specific selector discovery, more game strategies, and robust end-to-end prize/win verification.
- Only use game sites whose official rules explicitly permit automated play.
- CAPTCHA, anti-bot, anti-fraud, access-control, geolocation and payment safeguards are never bypassed. Detection pauses the run for a human.
- No login, signup, form submission, purchases, deposits, withdrawals, prize claims, or personal-data entry are implemented.
- No cookies or browser profile are imported or persisted. This runtime starts logged out.
- To use the local provider, install Ollama on the computer running this browser agent, start `ollama serve`, and pull a vision-capable model such as `ollama pull qwen2.5vl:3b`. This downloads model weights to your computer; inference is local and has no per-call API charge. Hardware needs depend on the selected model. The provider is implemented and tested but is not yet connected to the general site runner.

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

Text such as “2048”, “score”, or “play game” is never enough to identify a playable game. Multiple or malformed candidates return no game type. Detection is metadata only: it does not automatically click or play. The matching site's selectors and player configuration still need to be reviewed before using a dedicated adapter; arbitrary canvas-only boards and games without these explicit attributes remain unsupported.
