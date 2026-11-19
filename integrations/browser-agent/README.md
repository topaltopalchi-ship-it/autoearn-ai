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

## Current stage and boundaries

- **Implemented:** isolated Chromium context; exact HTTPS origin allowlist; bounded same-origin page traversal; duplicate/loop avoidance; visible link/button discovery; limited in-page expansion of folder-like controls; same-origin iframe inspection; heuristic folder/game/help/login/verification classification; limited safe button/link and keyboard adapter actions; and page/depth/time/interaction budgets.
- **Implemented for one game only:** bounded expectimax 2048 strategy, a defensive configurable DOM-to-board adapter, and a separate guarded runner that can execute and verify arrow-key moves when the site's board selectors are configured.
- **Implemented but not yet configured:** an optional OpenAI Responses API decision provider. It can send a bounded text observation and optional PNG/JPEG/WebP screenshot, accepts only allowlisted keyboard actions, and enforces a per-instance model-call budget. It is not wired into the 2048 runner and no API key/model is configured by default.
- **Not yet implemented:** reliable classification across arbitrary sites, automatic site-specific selector discovery, strategies for other games, and robust end-to-end prize/win verification. The 2048 runner has not yet been tested against a live third-party game site.
- Only use game sites whose official rules explicitly permit automated play.
- CAPTCHA, anti-bot, anti-fraud, access-control, geolocation and payment safeguards are never bypassed. Detection pauses the run for a human.
- No login, signup, form submission, purchases, deposits, withdrawals, prize claims, or personal-data entry are implemented.
- No cookies or browser profile are imported or persisted. This runtime starts logged out.
- No model API key is configured. The optional provider must run only in the isolated trusted worker, with explicit user approval, a model-call budget, and server-side secret storage; it is not enabled by default.
