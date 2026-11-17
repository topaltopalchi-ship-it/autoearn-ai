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
| Security, testing and release readiness | 14% | 68% | 9.5% | Owner authentication on API routes, no-store cache policy for dashboard/API responses, browser security headers, owner-only SQLite database file permissions with symlink rejection, private evidence upload/download rejecting symlinked files and directories, symlink-safe integrity-checked local SQLite/evidence backup and non-destructive checksum-verified restore, dependency consistency, a clean pip-audit scan, syntax checks and a passing Python 3.10/3.12/3.14 CI matrix are verified. Malware scanning, automated off-site backup and retention policy, periodic restore drills, independent security review, production secret/session design and deployment hardening remain. |
| **Total** | **100%** |  | **81.2%** | **18.8% engineering work remains. Production release is not yet approved.** |

Calculation: sum of (workstream weight × verified completion). Values are conservative engineering estimates and will only change when acceptance evidence changes.

## Release blockers — must not be represented as complete

1. No real competition or earning-platform adapter is installed. Real external submissions remain unavailable by design.
2. No automatic earnings or guaranteed payment exists. Ledger records and uploaded receipts are owner-provided evidence until independently reconciled.
3. Automatic retry is deliberately disabled for non-idempotent competition submissions because a timeout can leave the remote outcome ambiguous. The SQLite-backed rolling-minute limit is cross-worker; the owner must verify the remote platform before any manual retry.
4. Independent security review, malware scanning, evidence retention/backup policy, and production deployment review are outstanding.
5. Owner must manually confirm their country, platform eligibility, terms, and usable payout route using authoritative evidence.

## Latest verification

- Latest verified implementation commit: `24484355162e2dd1599a88ae382b4fda588ad9f0`.
- GitHub Actions run [44163708593](https://github.com/topaltopalchi-ship-it/autoearn-ai/actions/runs/44163708593): **286 tests passed on each of Python 3.10, 3.12 and 3.14**; includes conditional RSS caching/304 handling, private SQLite file-permission and symlink-rejection tests, symlink-safe evidence upload/download and backup/restore tests, security-header/CSP and no-store cache coverage, Python/JavaScript syntax checks, dependency consistency, and `pip-audit` reporting no known vulnerabilities. Weekly Dependabot updates are configured for Python packages and GitHub Actions.
- Later documentation-only updates must receive their own CI verification before release.
- `main` remains unchanged; PR #47 remains draft and unmerged; repository visibility remains public.
