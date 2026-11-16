# Project status

Last reviewed: 2026-11-16

This is an engineering estimate against a practical, local-first AutoEarn AI MVP scope. Percentages are milestone estimates, not measured code coverage or a claim that the product is production-ready.

## Estimated progress

| Workstream | Estimate | Evidence and remaining work |
|---|---:|---|
| Core API, data model, and reward/task tracking | 80% | FastAPI and SQLite endpoints exist; continue API integration and end-to-end validation. |
| Opportunity discovery | 70% | Provider adapters, category expansion, normalization, and deduplication exist; verify live provider behavior and terms. |
| Risk checks and human approval | 80% | Heuristic risk flags, review inbox, and approval gates exist; improve validation and edge-case coverage. |
| Dashboard and Persian RTL | 85% | Persian labels, dynamic statuses, currency formatting, RTL desktop/mobile layout, and Chromium smoke coverage now pass in CI; visual review on real devices remains open. |
| Automated tests and CI | 80% | Latest CI run 43867717186 passed: 75 tests, including Chromium desktop/mobile, translation preservation, form interaction, and the task approval flow. One third-party deprecation warning remains. |
| AI-assisted ranking and guidance | 25% | Explainable heuristic scoring exists; a full AI-assisted analysis/recommendation layer is not complete. |
| Deployment, monitoring, and production readiness | 15% | Hosting intentionally remains undecided; no production deployment or live earnings verification. |

**Overall MVP estimate: approximately 68%.** This is a revised engineering estimate reflecting the newly green browser validation and expanded regression coverage. It is not measured code coverage or a claim that the product is production-ready.

## Current engineering facts

- The project is local-first and does not guarantee income.
- Discovery candidates remain unverified and require human review; accepting a candidate is only a triage decision and does not create or activate an opportunity.
- Page-text extraction analyzes text supplied by the user; it does not fetch candidate URLs automatically.
- No automatic gameplay, ad clicks/views, spam, referrals, account creation, or other reward manipulation is added.
- Hosting provider remains undecided.
- Pull requests #1–#4 are open and unmerged. PR #4 is a draft stacked on PR #3.
- The Persian translation observer avoids rewriting already-translated text/attributes. Chromium coverage checks desktop/mobile RTL layout, dynamic-string translation, preservation of user-entered/external text, dialog interaction, and the human approval flow.
- Mwmbl documentation does not assert unverified anonymous-access quotas or authentication requirements; live access and current terms remain to be verified.
- CI triggers are scoped to avoid duplicate runs for feature-branch commits: feature work is validated by its pull-request workflow, while pushes to main/develop retain push validation.

## Latest validation

- Workflow run: https://github.com/topaltopalchi-ship-it/autoearn-ai/actions/runs/43867717186
- Job: `test` — success.
- Chromium installation: success.
- `pytest -q`: 75 passed, 1 third-party deprecation warning.
- The browser test includes desktop and mobile RTL assertions, translation behavior, opportunity creation, task creation, pending approval, and explicit approval.

## Next milestones

1. Expand browser coverage for discovery results and reward ledger interactions.
2. Verify the live search provider and document applicable API/data terms.
3. Complete AI-assisted opportunity analysis with explainable evidence and human review.
4. Perform security/privacy review and only then decide hosting and deployment.
