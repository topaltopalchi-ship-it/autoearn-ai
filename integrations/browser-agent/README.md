# AutoEarn isolated browser game agent

This is a separate Node.js runtime. It is not loaded by the public website and does not receive Supabase credentials.

## Setup

```sh
cd integrations/browser-agent
npm install
npx playwright install chromium
```

Set `AUTOEARN_GAME_URL` to the game URL and `AUTOEARN_ALLOWED_ORIGINS` to a comma-separated list of exact HTTPS origins that have been reviewed and explicitly permit automated play. The origin must match exactly; wildcards are not supported.

```sh
AUTOEARN_GAME_URL=https://example-game.invalid/play \
AUTOEARN_ALLOWED_ORIGINS=https://example-game.invalid \
npm start
```

The runtime opens a fresh isolated browser context, inspects the page's accessibility tree, and exposes a small action allowlist (exact accessible-name button clicks and a limited keyboard set). It stops if it detects common CAPTCHA / bot-verification interstitials, navigates off the approved origin, reaches its step/time budget, or cannot verify a move.

## Important boundaries

- Only use game sites whose official rules explicitly permit automated play. Add only the exact approved origin to the allowlist.
- CAPTCHA, anti-bot, anti-fraud, access-control, geolocation and payment safeguards are not solved, hidden, or bypassed. Detection pauses the run for a human.
- No login, signup, form submission, purchases, deposits, withdrawals, prize claims, or personal-data entry are implemented.
- No cookies or browser profile are imported or persisted. This initial runtime starts logged out.
- This package deliberately has no model API key or decision provider yet. The next stage is a game-specific strategy adapter and an optional server-side model provider with explicit cost limits.
- A browser driver is not a winning strategy. A game-specific adapter must understand the game's state and verify the actual result.
