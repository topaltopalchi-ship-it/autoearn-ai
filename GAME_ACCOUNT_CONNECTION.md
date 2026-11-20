# Game account connection policy

## Current status

AutoEarn AI does not currently connect to third-party game accounts. Signing in to a game in another browser tab does not grant AutoEarn access to that account or its session.

There is no generic or platform-independent OAuth integration for game accounts. A real integration must be designed for one named platform and must use that platform's documented authorization flow.

## Requirements before implementing an integration

1. Identify the exact game/platform and review its current official terms and developer documentation.
2. Confirm that the platform offers an official OAuth or API authorization flow and that the intended use is permitted.
3. Request only the minimum scopes required. Prefer read-only scopes where possible.
4. Keep client secrets and refresh tokens on a trusted server-side component; never place them in browser code, opportunity notes, logs, or source control.
5. Use state and PKCE where supported, validate redirect URIs, protect tokens at rest, and provide disconnect/revocation handling.
6. Explain the requested access and obtain the owner's explicit consent before connecting.
7. Do not request passwords, one-time codes, recovery codes, session cookies, or browser profile data.
8. Do not bypass CAPTCHA, anti-cheat, regional eligibility, KYC, payment, rate-limit, or other platform safeguards.
9. Keep account linking separate from task completion and reward recording. Linking an account must never trigger gameplay, purchases, submissions, or reward claims.

## Required product behavior

- If official authorization is unavailable or the platform prohibits the intended automation, do not implement the integration.
- If a platform requires a human to complete a step, stop and ask the owner to do it directly on the official platform.
- Display the platform name, requested permissions, connection state, and a clear disconnect action.
- Never imply that account connection proves eligibility, legitimacy, or a future payout.

## Current implementation boundary

The MVP remains an owner-only opportunity and reward-tracking workspace. Third-party game account connection and autonomous third-party gameplay are not implemented. A platform-specific integration is a separate milestone and requires a named platform plus a documented permission review.
