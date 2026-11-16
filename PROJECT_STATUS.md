# Project status

Last reviewed: 2026-11-16

This is an engineering estimate against a practical, local-first AutoEarn AI MVP scope. Percentages are milestone estimates, not measured code coverage or a claim that the product is production-ready.

## Estimated progress

| Workstream | Estimate | Evidence and remaining work |
|---|---:|---|
| Core API, data model, and reward/task tracking | 80% | FastAPI and SQLite endpoints exist; continue API integration and end-to-end validation. |
| Opportunity discovery | 70% | Provider adapters, category expansion, normalization, and deduplication exist; verify live provider behavior and terms. |
| Risk checks and human approval | 80% | Heuristic risk flags, review inbox, and approval gates exist; improve validation and edge-case coverage. |
| Dashboard and Persian RTL | 80% | Persian labels, dynamic statuses, currency formatting, RTL desktop/mobile CSS, and browser smoke test added; browser test is not yet green. |
| Automated tests and CI | 65% | Python suite has 74 passing tests in the last completed run; new Chromium smoke test exposed a root-page rendering issue that has been fixed in code and is awaiting a green rerun. |
| AI-assisted ranking and guidance | 25% | Explainable heuristic scoring exists; a full AI-assisted analysis/recommendation layer is not complete. |
| Deployment, monitoring, and production readiness | 15% | Hosting intentionally remains undecided; no production deployment or live earnings verification. |

**Overall MVP estimate: approximately 65%.** The estimate weights core product functionality more heavily than deployment polish. A production-ready release is substantially less complete because live provider verification, operational deployment, security review, and end-to-end browser validation remain open.

## Current engineering facts

- The project is local-first and does not guarantee income.
- Discovery candidates remain marked unverified and require human review.
- Page-text extraction analyzes text supplied by the user; it does not fetch candidate URLs automatically.
- No automatic gameplay, ad clicks/views, spam, referrals, account creation, or other reward manipulation is intended.
- Hosting provider remains undecided.
- Pull requests #1–#4 are open and unmerged. PR #4 is a draft stacked on PR #3.
- The latest browser CI run is pending completion; do not treat the new browser test as passed until GitHub Actions reports success.

## Next milestones

1. Get the Chromium desktop/mobile RTL smoke test green.
2. Expand browser coverage for discovery, user-entered text preservation, and approval flows.
3. Verify the live search provider and document applicable API/data terms.
4. Complete AI-assisted opportunity analysis with explainable evidence and human review.
5. Perform security/privacy review and only then decide hosting and deployment.