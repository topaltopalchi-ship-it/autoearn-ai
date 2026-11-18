# Production deployment gate

AutoEarn AI is a local-first, single-owner MVP. A passing CI run is not approval to expose it to the public internet. Keep the service bound to loopback or behind a private network until every gate below has an owner and verifiable evidence.

## Required before any public deployment

- [ ] Replace the single shared owner-token model with a reviewed identity and session design. Define login, logout, session expiry, revocation, rotation, brute-force controls, and account recovery.
- [ ] If browser cookies are introduced, implement and test CSRF protection, SameSite policy, secure cookies, origin checks, and session fixation defenses. Do not assume a custom header token is equivalent to a production session.
- [ ] Terminate HTTPS at a maintained reverse proxy or platform edge; redirect HTTP to HTTPS and enable HSTS only after HTTPS is confirmed end-to-end.
- [ ] Inject secrets through the hosting provider's secret manager. Never commit secret values, put them in image layers, expose them in frontend assets, or print them in logs. Document rotation and incident response.
- [ ] Restrict network ingress to the intended proxy; do not expose the application server or database directly. Set trusted proxy handling explicitly.
- [ ] Run the service as a dedicated unprivileged OS identity. Keep the SQLite database, receipt evidence, backups, and temporary files outside the web root with least-privilege permissions.
- [ ] Define encrypted off-device backup, retention, access control, restore objectives, and scheduled restore drills. Verify recovery of both the database and evidence files together.
- [ ] Provision and harden ClamAV `clamd` with loopback-only access at `127.0.0.1:3310`, maintained signatures, resource limits, health monitoring, and alerting. The application now fails closed before storing evidence unless it receives an exact clean verdict; scanner provisioning is external and is not performed by the app.
- [ ] Run live end-to-end scanner tests in an isolated environment (clean fixture accepted, EICAR rejected, scanner outage rejected) and verify no rejected upload is stored.
- [x] Reconcile stale unreferenced evidence files at startup by moving old regular non-symlink orphans into a private `.quarantine` directory without deleting them; referenced and fresh files are skipped.
- [ ] Define and test quarantine retention, audit/manifest, restore, and cleanup procedures; review the treatment of legacy `unscanned` evidence records. Startup orphan reconciliation is not a malware-quarantine workflow.
- [ ] Establish dependency update, vulnerability response, log redaction, monitoring, alerting, and incident-response procedures.
- [ ] Complete an independent security review and record findings and remediation evidence.
- [ ] For every external platform integration, obtain written permission, confirm current terms and country eligibility, use official least-privilege API scopes, and validate in a provider sandbox before enabling any live action.
- [ ] Independently reconcile payment evidence before treating ledger entries as verified earnings.

## Operational safety

- Keep the global execution pause enabled by default.
- Do not enable live external actions merely because an adapter is technically available.
- Do not store passwords, payment-card details, wallet private keys, or recovery phrases in AutoEarn.
- Never describe estimates, owner-entered ledger records, or uploaded receipts as independently verified income.
- If any required gate is incomplete, keep deployment private/local and mark production release as blocked.

## Sign-off record

Record the reviewer, date, deployment environment, evidence links, unresolved findings, and explicit approval for each gate before release. This checklist does not itself constitute a security audit or deployment approval.

## Evidence scanner deployment note

The evidence upload path calls a local ClamAV INSTREAM client. Start and health-check ClamAV before AutoEarn; if the daemon is absent or returns anything other than the exact clean verdict, uploads fail with HTTP 503 and are not stored. Do not expose the ClamAV TCP port to any network beyond loopback. Startup reconciliation also moves stale, unreferenced regular evidence files into a private `.quarantine` directory without deleting them. Retention and restore procedures remain incomplete. This filesystem consistency safeguard is distinct from malware scanning. See [Evidence malware scanning](EVIDENCE_MALWARE_SCANNING.md) for the tested behavior and remaining operational acceptance items.

## Quarantine backup/restore verification

The local backup and restore scripts recursively preserve nested evidence paths, including orphan files under `.quarantine`, and validate their manifest checksums. Backup creation and restore both reject Windows-reserved/invalid names and case/Unicode-normalization collisions; restore tests construct tampered manifests to verify restore-time rejection independently. Tests also verify owner-only POSIX permissions, rejection of unlisted extra files, and rejection of symlinks in the evidence tree. Backup creation now validates the database basename as a portable filename, and restore independently rejects unsafe or Windows-reserved database names in a tampered manifest. GitHub Actions run [44278688833](https://github.com/topaltopalchi-ship-it/autoearn-ai/actions/runs/44278688833) passed all Python 3.10, 3.12, and 3.14 jobs for commit `04b68d864d6761cc0f34124c110e57125155ec53`; the full suite reported 542 passed, 2 skipped, and 15 subtests passed. Lone-surrogate Unicode names in tampered restore manifests and undecodable POSIX evidence filenames are also covered by rejection tests. This verifies preservation and validation only: it does not complete retention, audit, recovery approval, or cleanup policy, and it does not convert quarantined files into clean evidence.
