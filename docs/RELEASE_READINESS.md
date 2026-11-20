# Release readiness snapshot

Checked: 2026-11-20 (UTC)
Branch: `develop`
Validated commit: `5426d14db61ca32b50befc2374a5432e95acd340`

## Automated validation

- GitHub Actions CI: passed, including JavaScript, browser-agent, Deno, Python, PostgreSQL lifecycle integration, and the pinned Zoa Docker build.
- Python tests workflow: passed.
- Static workspace smoke tests include element-ID, owner-only UI, script ordering, security-header, and manual-deploy checks.

## Supabase production project

- Project status: `ACTIVE_HEALTHY`; PostgreSQL 17.
- Applied migration history currently contains only `20261118134402_create_autoearn_core_tables_with_owner_rls`.
- These migrations exist in `develop` but are not recorded as applied in production:
  - `20261120080000_enforce_owner_state_transitions`
  - `20261120100000_add_country_payout_metadata`
- No production migration was applied during this check.
- Security advisor warning: leaked-password protection is disabled. Enable it in Supabase Auth settings before public release.
- Performance advisor reports two currently unused indexes: `tasks_opportunity_idx` and `rewards_opportunity_idx`. This is informational; do not remove them without workload review.

## Hosting

- Netlify deploy workflow is manual-only (`workflow_dispatch`) and refuses refs other than `develop`.
- The workflow requires `NETLIFY_AUTH_TOKEN` and `NETLIFY_SITE_ID` repository secrets.
- Secret presence and a production Netlify deploy were not verified in this check.
- No production deploy was performed.

## Release gates still requiring owner action

1. Enable leaked-password protection in Supabase Auth and re-check the security advisor.
2. Review the two pending SQL migrations against the production schema and approve their application explicitly.
3. Confirm Netlify site configuration and required GitHub Actions secrets; deploy only after explicit authorization.
4. Run deployed-site smoke tests for sign-in, discovery, manual opportunity entry, task lifecycle, reward ledger, metadata, and sign-out.
5. Select the first external platform and verify official country, payout, OAuth/API, and automation terms before implementing any connector.

## Product and safety boundaries

- Opportunities are auto-approved for manual opening; this does not verify legitimacy, payout, country eligibility, or automation permission.
- Task completion remains subject to human approval.
- No unattended third-party reward farming, CAPTCHA/anti-bot bypass, KYC or geographic restriction bypass, deposits, purchases, or automatic prize claims.
- No paid hosted AI API is required; local Ollama or deterministic decisions remain the supported paths.
- Revenue is not guaranteed.
