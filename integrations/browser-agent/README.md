# AutoEarn isolated browser game agent

This is a separate Node.js runtime. It is not loaded by the public website and does not receive Supabase credentials.

## Setup

```sh
cd integrations/browser-agent
npm install
npx playwright install chromium
npm test
```

Set `AUTOEARN_GAME_URL` to a game-site URL and `AUTOEARN_ALLOWED_ORIGINS` to the exact HTTPS origin reviewed and explicitly approved for automated play.

```sh
AUTOEARN_GAME_URL=https://example-game.invalid/arcade \\
AUTOEARN_ALLOWED_ORIGINS=https://example-game.invalid \\
npm start
```

The browser runtime now inspects the accessibility tree and lists visible, same-origin links and buttons that may represent folders, categories, rooms, or game entries. It filters out obvious account, payment, prize-claim, and destructive actions. The adapter can click a uniquely named safe same-origin link or a non-sensitive button, which allows a later strategy to open nested folders and inspect the next page.

## Current stage and boundaries

- **Implemented:** isolated Chromium context, exact HTTPS origin allowlist, folder/category target discovery, limited safe navigation actions, keyboard allowlist, step/time budgets, and basic verification-gate detection.
- **Not yet implemented:** autonomous AI decision-making, game-specific strategies, reliable folder-vs-game classification, and end-to-end gameplay. The runner currently discovers targets and stops; it does not yet choose or click them.
- Only use game sites whose official rules explicitly permit automated play.
- CAPTCHA, anti-bot, anti-fraud, access-control, geolocation and payment safeguards are never bypassed. Detection pauses the run for a human.
- No login, signup, form submission, purchases, deposits, withdrawals, prize claims, or personal-data entry are implemented.
- No cookies or browser profile are imported or persisted. This runtime starts logged out.
- No model API key or decision provider is configured. A model provider, if later added, must run server-side with explicit user approval and cost limits.
