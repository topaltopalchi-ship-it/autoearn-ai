# AutoEarn AI — Release acceptance and progress matrix

This matrix is the single source of truth for progress reports. Percentages measure verified engineering acceptance, not the number of commits or tests. A green test run verifies the tested behavior only; it does not by itself complete a product area.

## Weighted progress

| Workstream | Weight | Verified completion | Weighted contribution | Evidence / remaining acceptance |
|---|---:|---:|---:|---|
| Core foundation and opportunity evaluation | 18% | 95% | 17.1% | Category model, normalization, deterministic evaluation, confidence/risk, ranking, evidence freshness, AI suitability and tests are implemented. Final integration polish remains. |
| Discovery and source research | 18% | 95% | 17.1% | Manual intake, safe RSS/Atom, approved-feed scheduling, leases, feed health, pending review, source disable/reject, SQLite-persisted 60-second per-feed cooldown, durable exponential retry/backoff, and persisted ETag/Last-Modified conditional requests with HTTP 304 handling are implemented. Broader real-feed compatibility and adapter coverage remain. |
| Country, eligibility and payout readiness | 14% | 90% | 12.6% | Unknown-safe country eligibility, evidence URLs, payout capability, owner payout-route gate, fee/threshold/currency handling and tests are implemented. Real owner/platform-specific evidence still needs to be entered and reviewed. |
| Competition planning and integration | 12% | 67% | 8.0% | Deterministic/optional AI planning, intake, dry-run history, official API registry, exact-host allowlist, terms/eligibility checks, explicit confirmation and dashboard access to durable submission history (including unresolved write-ahead attempts) are implemented. A real platform adapter with written permission, official scopes and sandbox validation is not installed. |
| Supervised execution and controls | 14% | 70% | 9.8% | Persistent approval queue, human decisions, audit history, serialized decisions, global pause for competition submission, SQLite-backed cross-worker per-adapter rolling-minute limits, concurrent-request serialization and write-ahead submission-intent records committed before external API calls are implemented. Ambiguous attempts are never auto-retried; shared pause coverage is required for any future external-action surface. |
| Earnings ledger and reconciliation | 10% | 70% | 7.0% | Currency-separated ledger, constrained transitions, audit history, private PDF/PNG/JPEG receipt upload/list/download, file signature and size limits are implemented. Independent reconciliation with authoritative payment evidence and any payout integration remain. |
| Security, testing and release readiness | 14% | 71% | 9.9% | Owner authentication on API routes, persistent per-client sliding-window rate limiting after 10 failed attempts in five minutes, same-origin validation for browser state-changing API requests when an Origin header is present, no-store cache policy for dashboard/API responses, browser security headers, owner-only SQLite database file permissions with symlink rejection, private evidence upload/download rejecting symlinked files and directories, symlink-safe integrity-checked local SQLite/evidence backup and non-destructive checksum-verified restore, fixed-host TLS for the optional AI planning request, defused XML parsing for untrusted RSS/Atom feeds, explicit owner logout and local clearing of rejected session-scoped tokens, dependency consistency, a clean pip-audit scan, Bandit static analysis, syntax checks and a passing Python 3.10/3.12/3.14 CI matrix are verified. Client-side token clearing is not a server-side expiring/revocable production session. The bounded ClamAV INSTREAM client is integrated into evidence uploads: only an exact clean verdict is stored and list/download routes expose only clean records; detections and scanner outages fail closed. Production ClamAV provisioning, loopback-only daemon hardening, live EICAR integration tests, signature freshness monitoring, durable quarantine/retention/reconciliation, automated off-site backup, periodic restore drills, independent security review, production secret/session design and deployment hardening remain. |
| **Total** | **100%** |  | **81.6%** | **18.4% engineering work remains. Production release is not yet approved.** |

Calculation: sum of (workstream weight × verified completion). Values are conservative engineering estimates and will only change when acceptance evidence changes.

## Release blockers — must not be represented as complete

1. No real competition or earning-platform adapter is installed. Real external submissions remain unavailable by design.
2. No automatic earnings or guaranteed payment exists. Ledger records and uploaded receipts are owner-provided evidence until independently reconciled.
3. Automatic retry is deliberately disabled for non-idempotent competition submissions because a timeout can leave the remote outcome ambiguous. The SQLite-backed rolling-minute limit is cross-worker; the owner must verify the remote platform before any manual retry.
4. Production ClamAV daemon provisioning and hardening, live clean/EICAR/outage integration acceptance, scanner health and signature-freshness monitoring, durable evidence quarantine/retention/reconciliation, independent security review, and production deployment review are outstanding. The fail-closed upload integration itself is implemented; it is not production-accepted until the operational gates are verified.
5. Owner must manually confirm their country, platform eligibility, terms, and usable payout route using authoritative evidence.

## Latest verification

- Latest verified implementation commit: `073ca4841dedfe1e9d5c0817c9fbd5b96f473b62`. This includes strict backup/restore validation that rejects a malformed existing `earnings_evidence` schema instead of silently treating database errors as an empty evidence list.
- GitHub Actions run [44247543588](https://github.com/topaltopalchi-ship-it/autoearn-ai/actions/runs/44247543588), on commit `073ca4841dedfe1e9d5c0817c9fbd5b96f473b62`: all three Python matrix jobs (3.10, 3.12 and 3.14) completed successfully. Each test log reports **408 passed, 2 skipped, 1 warning, and 3 subtests passed**. This verifies the covered code paths only; it does not install or validate a real external competition adapter, authorize a live submission, or verify payout.
- Production deployment controls and sign-off requirements are documented in `docs/PRODUCTION_DEPLOYMENT_CHECKLIST.md`; the checklist is not yet satisfied.
- Later documentation-only updates must receive their own CI verification before release.
- `main` remains unchanged; PR #47 remains draft and unmerged; repository visibility remains public.
