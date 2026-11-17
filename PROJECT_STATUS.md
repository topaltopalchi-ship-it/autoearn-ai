# AutoEarn AI — Project Status & Handoff

_Last updated: 2026-11-17_

## Product direction

AutoEarn AI is a **private, single-owner, local-first personal assistant** for discovering, evaluating, and tracking legitimate online earning opportunities. It is not intended to be a public SaaS, multi-tenant service, or product for resale.

The repository's current README describes the project as a transparent opportunity discovery and reward-tracking workspace. It explicitly does not promise income or automate clicks, spam, or platform activity.

## Core principles

- Private, single-user operation; prefer localhost-only deployment.
- Keep secrets out of source control, logs, screenshots, and ordinary backups.
- Never invent reward amounts, eligibility, or payout terms; mark unknown facts as unverified.
- Human approval is required before promoting a discovered lead or taking consequential actions.
- No automatic clicking, spam, deceptive activity, or actions that violate a platform's rules.
- Do not store wallet seed phrases or wallet private signing keys in the application. Use public wallet addresses where a receiving address is sufficient.
- Keep changes on feature branches and use pull requests; do not change `main` without explicit approval and verified checks.

## Intended capabilities

1. Discover opportunities from permitted sources.
2. Rank candidates for human review using evidence, confidence, eligibility, reward details, and risk.
3. Let the owner accept/reject candidates and explicitly promote accepted candidates into a personal opportunity tracker.
4. Prevent duplicate promotions and preserve source URLs and provenance.
5. Track status, deadlines, verified rewards, expenses, and net results.
6. Manage AI/search provider API credentials in a protected local vault.
7. Test provider connectivity without exposing credentials.
8. Create and restore encrypted backups.
9. Provide a private dashboard and, later, a personally controlled bot interface.

## Security requirements before real credentials

- Confirm authentication protects every sensitive API route, not just the dashboard.
- Bind local development/server defaults to `127.0.0.1`; document any deliberate remote deployment separately.
- Use authenticated encryption for stored credentials and a strong key-management design. Do not hard-code encryption keys.
- Redact secrets from responses, logs, errors, telemetry, and test output.
- Validate credential type and provider; reject wallet seed phrases/private keys rather than treating them as ordinary API keys.
- Test backup/restore, wrong-password behavior, tampering detection, and key rotation/recovery.
- Do not enter production credentials until security tests and a manual review pass.

## Development history noted in the previous working conversation

The prior handoff reported work in these areas. Treat these as **historical claims that must be checked against the current branches, PR diffs, and Actions results before relying on them**:

- Candidate ranking and human-review prioritization.
- Candidate-to-opportunity promotion with duplicate protection and explicit user approval.
- Local/private-use documentation and localhost-oriented startup guidance.
- Credential vault, provider connection testing, and encrypted backup/restore work.
- Wallet-secret detection and rejection safeguards.
- CI workflow updates intended to cover feature branches.

PR numbers previously mentioned: #39 (credential/wallet safeguards) and #40 (CI workflow coverage). Their current state, exact contents, and check results have not been verified as part of this status-file creation.

## Immediate next steps

1. Reconcile open PRs and feature branches; inspect actual diffs and latest commit SHAs.
2. Confirm CI triggers on pushes and pull requests for the intended branches, and verify that checks actually run.
3. Run the complete test suite on the current candidate branch; fix failures based on logs rather than assumptions.
4. Audit authentication and authorization on every credential, backup, restore, and opportunity API endpoint.
5. Complete and manually verify encrypted vault backup/restore and secret redaction.
6. Complete provider adapters (starting with AI and search) that read credentials from the vault without returning them to the browser.
7. Finish the private opportunity/account tracking workflow and produce an install/run guide for the owner's machine.

## Release gate

Do not call the application ready for real credentials or real-money activity until the relevant tests pass, the security review is complete, backup restoration is verified, and the owner has reviewed the deployment exposure. Keep `main` unchanged until the owner explicitly approves a merge.
