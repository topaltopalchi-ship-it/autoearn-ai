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

The crawler performs a bounded breadth-first walk of same-origin HTTPS links. It records visited pages, titles, navigation targets, and a preliminary page classification; avoids URL loops; and inspects links found in same-origin iframes. Playwright supports iframe interaction and open Shadow DOM through locators; closed Shadow DOM is not supported. See [Playwright locators](https://playwright.dev/docs/locators), [frames](https://playwright.dev/docs/frames), and [locator ARIA snapshots](https://playwright.dev/docs/api/class-locator).

Configure optional bounds with `AUTOEARN_MAX_PAGES` (default 12, maximum 30), `AUTOEARN_MAX_DEPTH` (default 3, maximum 6), and `AUTOEARN_MAX_DURATION_MS` (default 60 seconds, maximum 5 minutes).

## Page classification

Each visited page is heuristically labeled as `folder`, `game`, `help`, `login`, `verification`, or `unknown`. The result includes a confidence estimate and signal list. It uses title/text, visible navigation labels, and DOM signals such as canvas and score indicators. These are clues, not proof: sites can use custom canvases, misleading labels, or inaccessible controls. A human or a site-specific adapter must validate the classification before play.

## Current stage and boundaries

- **Implemented:** isolated Chromium context; exact HTTPS origin allowlist; bounded same-origin page traversal; duplicate/loop avoidance; visible link/button discovery; same-origin iframe inspection; heuristic folder/game/help/login/verification classification; limited safe button/link and keyboard adapter actions; and page/depth/time budgets.
- **Not yet implemented:** autonomous AI decision-making, reliable classification across arbitrary sites, game-specific control mapping, gameplay strategy, and end-to-end win verification. The current runner maps and classifies pages; it does not yet choose a game or play it.
- Only use game sites whose official rules explicitly permit automated play.
- CAPTCHA, anti-bot, anti-fraud, access-control, geolocation and payment safeguards are never bypassed. Detection pauses the run for a human.
- No login, signup, form submission, purchases, deposits, withdrawals, prize claims, or personal-data entry are implemented.
- No cookies or browser profile are imported or persisted. This runtime starts logged out.
- No model API key or decision provider is configured. A model provider, if later added, must run server-side with explicit user approval and cost limits.
