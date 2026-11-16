# AutoEarn AI roadmap

## Product direction

AutoEarn AI is a private, single-owner, human-in-the-loop assistant for one person's discovery and evaluation of online opportunities. It is not intended to be offered to other users.

## MVP 0.1 (this branch)

- [x] Local SQLite persistence
- [x] Opportunity registry with eligibility and terms fields
- [x] Transparent completeness score (not a legitimacy guarantee)
- [x] Task queue with explicit approval before completion
- [x] Reward ledger and dashboard
- [x] API tests and GitHub Actions CI
- [x] Explainable opportunity-fit ranking using supplied reward, time, country, payout, and risk metadata (advisory only)
- [x] Deterministic net-return calculator with direct costs, percentage and flat fees, net hourly estimate, break-even threshold, and optional target hourly rate (same-currency only)

## Next milestones

1. **Discovery connectors:** opt-in search/provider integrations; source URL, checked-at timestamp, evidence excerpts, country eligibility, minimum age, payout threshold, and terms snapshot.
2. **Trust and risk review:** flag deposits, pay-to-unlock schemes, unclear ownership, excessive permissions, unverifiable payouts, and requests to evade regional/KYC controls. Never label a platform safe based only on its own marketing.
3. **Game assistance:** game-specific permitted helpers, strategy hints, accessibility support, and manual play guidance. No botting, fake engagement, anti-cheat evasion, multi-account abuse, or unattended reward farming.
4. **User approvals:** configurable confirmation for account linking, purchases, personal data, submissions, and reward claims.
5. **Reward reconciliation:** proof/reference uploads, pending/confirmed/paid/rejected states, and exportable history.
6. **Private single-owner security:** loopback-only local access, private secret storage, encrypted personal backups, and optional local authentication if the app is ever exposed beyond the owner's device. No public hosting or multi-user infrastructure is planned.

## Important limitations

- No earnings are guaranteed.
- Platform eligibility and terms vary by country and change over time.
- The MVP does not crawl the internet or play games autonomously.
- Do not enter passwords, payment details, identity documents, or API secrets into opportunity notes.

- [x] Evidence-based discovery review-priority queue (separate from income ranking; candidates remain unverified)

- [x] Document private single-owner operation and add loopback-only local launcher
