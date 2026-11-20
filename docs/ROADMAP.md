# AutoEarn AI roadmap

## Product direction

AutoEarn AI is a private, single-owner personal workspace for one account holder to discover, evaluate, and track reward opportunities. There is no public registration, multi-tenant onboarding, or plan to support additional users. The owner signs in with the one account created directly in Supabase. It supports manual participation and bounded local game-agent experiments. It does not promise income or perform unattended third-party reward farming.

## Implemented in develop

- [x] Owner-only Supabase Auth and RLS-backed opportunities, tasks, and rewards.
- [x] New and manually added opportunities are auto-approved for manual opening; no opportunity approval queue or independent-attestation gate.
- [x] Discovery pipeline with bounded public search requests, URL validation, duplicate handling, category exclusions, and informational review flags.
- [x] Evidence-completeness heuristic and opportunity sorting/comparison. Scores are disclosure signals, not legitimacy or payout verification.
- [x] Country and payout metadata fields, owner-entered evidence URLs, form validation, and UI disclosures. These fields do not gate manual access.
- [x] Reward ledger with separate currencies, status transitions, payment references, and monthly reporting. Owner-entered paid status is not bank verification.
- [x] Task queue with explicit human approval before marking a task complete.
- [x] Local puzzle lab and bounded game-agent loop with action allowlists, budgets, cancellation, and post-action verification.
- [x] Local Ollama/deterministic decision path; no paid hosted AI API is required.
- [x] Browser-agent navigation and page classification tests; game-specific adapters remain disabled unless exact official rules permit their actions.
- [x] Python, JavaScript, Deno, PostgreSQL lifecycle, and Zoa Docker build checks pass in CI.
- [x] Static Netlify deployment configuration and optional FastAPI health/static host.

## Remaining before production release

1. **Single-owner setup:** verify public sign-ups are disabled, retain only the owner's Supabase Auth account, confirm the publishable key and allowed site URL/redirect configuration, and verify sign-in/sign-out. Do not add user-management or multi-tenant features.
2. **Database release:** review and apply the pending migrations to the intended Supabase project only after explicit owner authorization. CI tests use an ephemeral PostgreSQL instance and do not update production.
3. **Hosting release:** configure the production Netlify site and deploy the approved branch only after explicit owner authorization. No production deploy has been performed by this work.
4. **Smoke test:** verify sign-in, opportunity discovery, manual add/edit, task transitions, reward ledger, country/payout metadata, and sign-out on the deployed site.
5. **First external platform:** select one named platform and verify its official OAuth/API documentation, country availability, payout terms, and exact automation permissions before building a connector. Until then, external accounts remain manual-only.
6. **Operational safeguards:** confirm backups, recovery procedure, rate limits, and audit expectations for the sole owner. Multi-user expansion is out of scope.

## Safety boundaries

- No automatic account creation, login, personal-data submission, deposits, purchases, prize claims, or gameplay on third-party platforms.
- Never request or store passwords, OTPs, seed phrases, browser cookies, or session tokens in the app.
- Never bypass CAPTCHA, anti-bot, anti-cheat, KYC, geographic restrictions, or platform access controls.
- An opportunity's `eligible` status means only that the owner may manually open its public HTTPS page. It does not prove legitimacy, cash payout, country eligibility, or permission to automate.
- Task completion requires human approval. Reward status and payment references are owner-entered and are not proof of bank settlement.
- All economics and evidence scores are estimates or text heuristics, not guarantees.
- No production migration or deployment is performed without explicit owner authorization.
