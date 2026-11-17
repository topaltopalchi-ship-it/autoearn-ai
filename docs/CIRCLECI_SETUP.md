# CircleCI setup for AutoEarn AI

CircleCI can run the repository's checks on hosted machines without changing
GitHub visibility. The repository may remain public during development and be
made private after the project is complete. The configuration uses the small
Docker resource class and does not save caches or upload artifacts.

## Included checks

- Python 3.10 dependency installation
- `pip check` dependency consistency
- Python syntax compilation for `app/`, `autoearn/`, and `tests/`
- Full pytest suite
- Node.js syntax validation for `static/app.js`

The jobs do not deploy the application, interact with earning platforms, or
perform account actions. No repository secrets or personal access tokens are
needed by the test jobs.

## Connect the GitHub repository

1. Open [CircleCI](https://circleci.com/) on your phone and sign up using the
   GitHub account that owns `topaltopalchi-ship-it/autoearn-ai`.
2. Authorize CircleCI to access the selected repository. Grant access only to
   `topaltopalchi-ship-it/autoearn-ai` if the GitHub authorization screen
   allows selecting individual repositories.
3. In CircleCI, choose the AutoEarn AI repository and select the option to
   set up a project using the existing `.circleci/config.yml`.
4. Start the first pipeline. CircleCI should detect the configuration file and
   run the Python and JavaScript jobs.
5. Confirm that both jobs pass. Do not change GitHub visibility just to set up CI.
   At final release, after making the repository private, verify that CircleCI
   still has access and rerun both jobs.

## Free-plan limits

CircleCI currently advertises a Free plan with 30,000 credits per month, up to
6,000 build minutes on the small Docker resource class, and up to five active
users. Limits and eligibility can change; review the official pricing page
before relying on the allowance:
[CircleCI pricing](https://circleci.com/pricing/).

The pipeline intentionally avoids cache and artifact retention to minimize
storage consumption. If the monthly credits are exhausted, hosted jobs pause
until the next monthly refill unless the account owner chooses a paid plan.

## Repository ownership and security

- GitHub remains the canonical repository and pull-request location.
- CircleCI receives access only after the repository owner authorizes it.
- Never paste a GitHub token, password, or recovery code into source files,
  issues, or chat.
- Do not change repository visibility solely to obtain CI minutes; keep the agreed public status during development and make it private only at final release.
- Keep PRs open until the first CircleCI run has completed and the changes
  have been reviewed.
