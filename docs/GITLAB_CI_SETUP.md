# Running AutoEarn AI checks with GitLab CI

This repository can remain private on GitHub. GitLab CI is an optional external
runner for the same test commands when the GitHub Actions included-minute quota
for a private repository is exhausted.

## Pipeline checks

The `.gitlab-ci.yml` pipeline runs:

- Python 3.10 dependency installation and `pip check`
- Python compile check for `app/`, `autoearn/`, and `tests/`
- The complete pytest suite
- JavaScript syntax validation for `static/app.js`

No deployment, external platform interaction, account creation, or opportunity
execution is performed by this pipeline. No secrets are required for these
checks. The pipeline intentionally does not upload artifacts or retain pip
caches, keeping storage usage low.

## Connect a private GitHub repository

1. Create a private project in GitLab by importing the existing GitHub
   repository. Keep project visibility set to **Private**.
2. Authorize GitLab to read the private GitHub repository using GitLab's
   supported GitHub import/mirror flow. Do not paste a personal access token
   into repository files, issues, or chat.
3. In the GitLab project, enable pull-mirror updates from GitHub if using
   scheduled/automatic pull mirroring.
4. Enable **Pipelines for mirror updates** in the repository mirroring
   settings, if that option is available for the project. Otherwise, trigger
   a pipeline manually after each mirror update.
5. Confirm the imported GitLab project is private and that a pipeline runs
   against the mirrored branch.

GitLab plan quotas and runner availability can change. Check the current
namespace usage and project CI/CD minutes before relying on the free tier.
Do not make this GitHub repository public to obtain free Actions minutes.

## Important

- GitHub remains the canonical repository and pull-request location.
- This file does not create a GitLab account, import the repository, or
  configure mirroring; those steps require the owner's GitLab authorization.
- Keep GitHub PRs open until the mirrored pipeline has been observed running
  successfully and the owner has reviewed the result.
