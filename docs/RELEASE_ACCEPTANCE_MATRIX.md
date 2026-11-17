# AutoEarn AI — Release acceptance and progress matrix

This matrix is the single source of truth for progress reports. Percentages measure verified engineering acceptance, not the number of commits or tests. A green test run verifies the tested behavior only; it does not by itself complete a product area.

## Weighted progress

| Workstream | Weight | Verified completion | Weighted contribution | Evidence / remaining acceptance |
|---|---:|---:|---:|---|
| Core foundation and opportunity evaluation | 18% | 95% | 17.1% | Category model, normalization, deterministic evaluation, confidence/risk, ranking, evidence freshness, AI suitability and tests are implemented. Final integration polish remains. |
| Discovery and source research | 18% | 90% | 16.2% | Manual intake, safe RSS/Atom, approved-feed scheduling, leases, feed health, pending review, source disable/reject, SQLite-persisted 60-second per-feed cooldown and durable exponential retry/backoff for failed read-only feeds are implemented. Feed-result caching remains. |
| Country, eligibility and payout readiness | 14% | 90% | 12.6% | Unknown-safe country eligibility, evidence URLs, payout capability, owner payout-route gate, fee/threshold/currency handling and tests are implemented. Real owner/platform-specific evidence still needs to be entered and reviewed. |
| Competition planning and integration | 12% | 65% | 7.8% | Deterministic/optional AI planning, intake, dry-run history, official API registry, exact-host allowlist, terms/eligibility checks and explicit confirmation are implemented. A real platform adapter with written permission, official scopes and sandbox validation is not installed. |
| Supervised execution and controls | 14% | 55% | 7.7% | Persistent approval queue, human decisions, audit history, serialized decisions, global pause for competition submission and in-process per-adapter rate limiting are implemented. Durable retry/backoff, distributed limits and a shared pause gate for any future external-action surface remain. |
| Earnings ledger and reconciliation | 10% | 70% | 7.0% | Currency-separated ledger, constrained transitions, audit history, private PDF/PNG/JPEG receipt upload/list/download, file signature and size limits are implemented. Independent reconciliation with authoritative payment evidence and any payout integration remain. |
| Security, testing and release readiness | 14% | 50% | 7.0% | Owner authentication on API routes, browser security headers, private evidence storage, dependency checks, syntax checks and a passing Python 3.10/3.12/3.14 CI matrix are verified. Malware scanning, retention/backup policy, independent security review, production secret/session design and deployment hardening remain. |
| **Total** | **100%** |  | **75.4%** | **24.6% engineering work remains. Production release is not yet approved.** |

Calculation: sum of (workstream weight × verified completion). Values are conservative engineering estimates and will only change when acceptance evidence changes.

## Release blockers — must not be represented as complete

1. No real competition or earning-platform adapter is installed. Real external submissions remain unavailable by design.
2. No automatic earnings or guaranteed payment exists. Ledger records and uploaded receipts are owner-provided evidence until independently reconciled.
3. Durable retry/backoff and multi-worker rate limiting are not complete. Do not retry non-idempotent submissions automatically.
4. Independent security review, malware scanning, evidence retention/backup policy, and production deployment review are outstanding.
5. Owner must manually confirm their country, platform eligibility, terms, and usable payout route using authoritative evidence.

## Latest verification

- Latest verified implementation commit: `3e4311174a518294cff7cc4793a9f075a0359789`.
- GitHub Actions run [44153612502](https://github.com/topaltopalchi-ship-it/autoearn-ai/actions/runs/44153612502): **261 passed on each of Python 3.10, 3.12 and 3.14**; dependency consistency, Python syntax and dashboard JavaScript syntax passed in all three jobs.
- Later documentation-only updates must receive their own CI verification before release.
- `main` remains unchanged; PR #47 remains draft and unmerged; repository visibility remains public.
