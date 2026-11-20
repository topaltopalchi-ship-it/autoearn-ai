# Release readiness snapshot

Checked: 2026-11-20 (UTC)
Branch: `develop`
Validated commit: `f62a9fd3bd95bbeda64c72b7a0d5b8cde7623de7`

## Automated validation

- GitHub Actions CI: passed on `f62a9fd3bd95bbeda64c72b7a0d5b8cde7623de7`, including JavaScript, browser-agent, Deno, Python, PostgreSQL lifecycle integration (including second-account isolation), and the pinned Zoa Docker build. Run: https://github.com/topaltopalchi-ship-it/autoearn-ai/actions/runs/44704487498
- Python tests workflow: passed on the same commit. Run: https://github.com/topaltopalchi-ship-it/autoearn-ai/actions/runs/44704487470
- Static workspace smoke tests include element-ID, owner-only sign-in surface, script ordering, security-header, and manual-deploy checks.

## Supabase production project

- Project status: `ACTIVE_HEALTHY`; PostgreSQL 17.
- Product mode: one private owner account only. The static app exposes password sign-in and sign-out, not public sign-up. The prepared `20261120120000_lock_workspace_to_single_owner` migration records the sole existing Auth user and adds restrictive RLS policies so any other authenticated account is blocked. It aborts unless exactly one Auth user exists at application time. Confirm public sign-ups remain disabled before release.
- Applied migration history currently contains only `20261118134402_create_autoearn_core_tables_with_owner_rls`.
- These migrations exist in `develop` but are not recorded as applied in production:
  - `20261120080000_enforce_owner_state_transitions`
  - `20261120100000_add_country_payout_metadata`
  - `20261120120000_lock_workspace_to_single_owner`
- No production migration was applied during this check.
- Security advisor warning: leaked-password protection is disabled. Enable it in Supabase Auth settings before public release.
- Performance advisor reports two currently unused indexes: `tasks_opportunity_idx` and `rewards_opportunity_idx`. This is informational; do not remove them without workload review.

### Auth warning remediation

The current Supabase documentation states that leaked-password protection is available on the Pro plan and above. In the Dashboard, open **Authentication → Sign In / Providers → Email**, then enable **Prevent use of leaked passwords** and save. If the project is on the Free plan, this control may be unavailable; do not treat the warning as evidence that an account password has leaked. As a fallback, set a minimum password length of at least 8 characters and require a stronger character mix in the same Email provider settings. Re-run the Security Advisor after any change.

Reference: https://supabase.com/docs/guides/auth/password-security

## Hosting

- Netlify deploy workflow is manual-only (`workflow_dispatch`) and refuses refs other than `develop`.
- The workflow requires `NETLIFY_AUTH_TOKEN` and `NETLIFY_SITE_ID` repository secrets.
- Secret presence and a production Netlify deploy were not verified in this check.
- No production deploy was performed.

## Release gates still requiring owner action

1. Verify public sign-ups are disabled and only the owner's account exists; strengthen password settings in Supabase Auth and re-check the security advisor. Leaked-password protection is Pro+ only.
2. Review the three pending SQL migrations against the production schema and approve their application explicitly. The single-owner lock requires exactly one existing Auth user.
3. Confirm Netlify site configuration and required GitHub Actions secrets; deploy only after explicit authorization.
4. Run deployed-site smoke tests for sign-in, discovery, manual opportunity entry, task lifecycle, reward ledger, metadata, and sign-out.
5. Select the first external platform and verify official country, payout, OAuth/API, and automation terms before implementing any connector. This is for the owner's own account only.

## Product and safety boundaries

- Opportunities are auto-approved for manual opening; this does not verify legitimacy, payout, country eligibility, or automation permission.
- Task completion remains subject to human approval.
- No unattended third-party reward farming, CAPTCHA/anti-bot bypass, KYC or geographic restriction bypass, deposits, purchases, or automatic prize claims.
- No paid hosted AI API is required; local Ollama or deterministic decisions remain the supported paths.
- Revenue is not guaranteed.
