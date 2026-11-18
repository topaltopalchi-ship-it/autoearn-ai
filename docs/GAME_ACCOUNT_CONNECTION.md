# Game account connection and permitted automation

## Goal

Let the owner connect a game account without giving AutoEarn an email password, then enable only game-specific assistance that the platform explicitly permits.

## Important browser boundary

Opening a game in another tab and signing into it with Gmail does not connect that signed-in session to AutoEarn. The current app is hosted on a different origin. Browser same-origin protections prevent its JavaScript from reading the game's page, cookies, local storage, or authenticated state. AutoEarn must never ask the owner to paste Gmail passwords, game passwords, session cookies, or one-time codes.

## Supported connection paths (in priority order)

1. **Official OAuth / account linking**: use the game's documented authorization endpoint, authorization-code flow with PKCE, exact redirect URI, state/nonce validation, minimum scopes, and token revocation. Store refresh tokens only server-side with encryption; never in browser localStorage or opportunity notes.
2. **Official game API**: use documented endpoints and rate limits. Keep tokens scoped to the one platform and owner account.
3. **No official connection**: show the platform as manual_only. The owner may open it and play manually, but AutoEarn must not claim the account is connected or that it can control the game.
4. **Permitted game-specific helper**: only after the platform's official rules explicitly allow the exact automation. Build and test a dedicated adapter for that game. Do not infer permission from silence or from a generic terms URL.

## Automation safety gates

An adapter may run only when all of these are true:

- The platform and exact game have been identified.
- An official source explicitly permits the intended automated actions.
- The account's country and prize payout route are confirmed from official sources.
- The owner has approved this specific session.
- The adapter uses documented APIs or an explicitly permitted interface.
- A visible stop control, action limits, and an audit trail are present.

Never automate CAPTCHA or anti-bot challenges, evade anti-cheat, fake engagement, create or rotate accounts, bypass regional restrictions/KYC, or perform unattended reward farming. Never spend money, claim a prize, or submit personal data without a separate owner confirmation.

## Planned implementation sequence

- [ ] Add a platform connection capability field: oauth, official_api, or manual_only.
- [ ] Add a server-side OAuth callback with PKCE/state validation for the first platform that publishes a supported OAuth/API specification.
- [ ] Add a connection status panel showing not_connected, connected, expired, or manual_only; do not expose tokens.
- [ ] Add a game adapter registry. Default every platform to disabled until a reviewed adapter and official permission evidence exist.
- [ ] Add per-session approval, visible stop, action/time limits, and an audit record.
- [ ] Add automated tests for redirect validation, state mismatch, token secrecy, expired sessions, and disabled adapters.

## Current implementation status

The current createTask() function only opens the official HTTPS URL in a new tab and records a guided task. It does not connect an account, read another site's login state, or play a third-party game. The built-in Puzzle Lab is a local demo and is not connected to external rewards.

## First platform requirement

Before implementing a real connector, select one specific game platform and verify that it offers official OAuth or a documented API, supports the owner's country, and explicitly permits the intended assistance. A Gmail login button by itself is not an integration API.
