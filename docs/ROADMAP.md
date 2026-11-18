# AutoEarn AI roadmap

## Product direction

AutoEarn AI is an owner-only workspace for discovering and evaluating legitimate reward-bearing games, connecting accounts through official authorization, and providing game-specific assistance only where platform rules explicitly permit it.

## MVP 0.1 (this branch)

- [x] Opportunity registry with eligibility and terms fields
- [x] Transparent completeness score (not a legitimacy guarantee)
- [x] Task queue with explicit approval before completion
- [x] Reward ledger and dashboard
- [x] Online text translator
- [x] Opportunity discovery and filtering
- [x] API tests and GitHub Actions CI

## Next milestones

1. **Discovery quality:** source URL, checked-at timestamp, evidence excerpts, country eligibility, minimum age, payout threshold, and official terms snapshot.
2. **Trust and risk review:** flag deposits, pay-to-unlock schemes, unclear ownership, excessive permissions, unverifiable payouts, and requests to evade regional/KYC controls. Never label a platform safe based only on its own marketing.
3. **Account connection:** official OAuth/API integrations only; never collect Gmail/game passwords or browser cookies. See GAME_ACCOUNT_CONNECTION.md.
4. **Game assistance:** game-specific permitted helpers, strategy hints, accessibility support, and manual play guidance. An adapter stays disabled unless the exact platform rules explicitly permit its actions.
5. **User approvals:** configurable confirmation for account linking, purchases, personal data, submissions, and reward claims.
6. **Reward reconciliation:** proof/reference uploads, pending/confirmed/paid/rejected states, and exportable history.
7. **Deployment and security:** authentication, encrypted secrets, audit log, rate limits, backups, and hosted database before multi-user operation.

## Important limitations

- No earnings are guaranteed.
- Platform eligibility and terms vary by country and change over time.
- The current app does not connect third-party game accounts or play third-party games autonomously.
- Signing into a game with Gmail in another tab does not grant AutoEarn access to that game's session.
- Do not enter passwords, payment details, identity documents, session cookies, or API secrets into opportunity notes.
- Never bypass CAPTCHA, anti-cheat, regional restrictions, or platform controls; no unattended reward farming.
