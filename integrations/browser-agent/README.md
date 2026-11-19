# AutoEarn isolated browser game agent

This is a separate Node.js runtime. It is not loaded by the public website and does not receive Supabase credentials.

## Setup

\`\`\`sh
cd integrations/browser-agent
npm install
npx playwright install chromium
npm test
\`\`\`

Set \`AUTOEARN_GAME_URL\` to the starting game-site URL and \`AUTOEARN_ALLOWED_ORIGINS\` to the exact HTTPS origin reviewed and explicitly approved for automated play.

\`\`\`sh
AUTOEARN_GAME_URL=https://example-game.invalid/arcade \\
AUTOEARN_ALLOWED_ORIGINS=https://example-game.invalid \\
npm start
\`\`\`

The crawler now performs a bounded breadth-first walk of same-origin HTTPS links. It records the visited pages, their titles, and visible navigation targets; avoids URL loops; and can inspect links found in same-origin iframes. Playwright locators also work through open Shadow DOM; closed Shadow DOM is not supported by Playwright. See the official [locator documentation](https://playwright.dev/docs/locators) and [frame documentation](https://playwright.dev/docs/api/class-page).

Configure optional bounds with \`AUTOEARN_MAX_PAGES\` (default 12, maximum 30), \`AUTOEARN_MAX_DEPTH\` (default 3, maximum 6), and \`AUTOEARN_MAX_DURATION_MS\` (default 60 seconds, maximum 5 minutes).

## Current stage and boundaries

- **Implemented:** isolated Chromium context; exact HTTPS origin allowlist; bounded same-origin page traversal; duplicate/loop avoidance; visible link/button discovery; same-origin iframe inspection; limited safe button/link and keyboard adapter actions; step/time/page/depth budgets; and basic verification-gate detection.
- **Not yet implemented:** autonomous AI decision-making, reliable semantic classification of every folder versus game, automated gameplay strategy, and end-to-end win verification. The current runner maps pages and stops; it does not yet choose games or play them.
- Only use game sites whose official rules explicitly permit automated play.
- CAPTCHA, anti-bot, anti-fraud, access-control, geolocation and payment safeguards are never bypassed. Detection pauses the run for a human.
- No login, signup, form submission, purchases, deposits, withdrawals, prize claims, or personal-data entry are implemented.
- No cookies or browser profile are imported or persisted. This runtime starts logged out.
- No model API key or decision provider is configured. A model provider, if later added, must run server-side with explicit user approval and cost limits.
