# Kaggle platform onboarding decision

## Initial platform selection

Kaggle is the first candidate platform for the competition vertical because it publishes an official CLI and public API documentation for listing competitions, downloading competition data, submitting files or code-kernel outputs, and checking submission status.

Official references:
- Terms of Use: https://www.kaggle.com/terms
- Public API and CLI: https://www.kaggle.com/docs/api
- Official CLI repository: https://github.com/Kaggle/kaggle-cli
- Competition command reference: https://github.com/Kaggle/kaggle-cli/blob/main/docs/competitions.md
- Submission tutorial: https://github.com/Kaggle/kaggle-cli/blob/main/docs/tutorials.md

This is a platform-selection decision, **not** authorization to submit to every Kaggle competition.

## Eligibility gates

1. The owner must use their own genuine Kaggle account and personally accept the platform and competition-specific rules.
2. The owner must verify their actual country of residence, age/identity requirements where applicable, sanctions/export-control restrictions, and the individual competition's eligibility and prize-delivery terms. The general Kaggle terms list certain excluded territories/countries, but competition sponsors can impose additional restrictions. Never infer residence from IP geolocation.
3. Each competition must be reviewed independently for whether AI assistance, automated agents, external compute, teams, and the proposed submission method are permitted.
4. An official CLI/API capability does not itself grant permission to automate participation. The adapter must remain disabled unless the relevant rules explicitly permit the proposed automated action.
5. Prize eligibility and payout-route availability are separate checks. A leaderboard position is not proof of prize eligibility or payment.

## Planned integration boundary

The first integration should be a narrow Kaggle adapter using only documented Kaggle CLI/API operations:
- read/list competitions and metadata;
- download competition data only after the owner has joined and accepted that competition's rules;
- prepare and validate candidate submission artifacts locally;
- inspect submission history and scoring status.

A public submission is a non-idempotent external action. It must remain disabled by default and require all of:
- owner-authenticated session;
- per-competition rules and country eligibility marked verified with evidence;
- explicit evidence that the competition permits the proposed AI/automation workflow;
- approved exact host and documented API/CLI capability;
- global emergency pause cleared;
- fresh, per-submission owner confirmation.

Do not automate browser login, CAPTCHA, account creation, rule acceptance, identity declarations, or payout/withdrawal flows. Do not store Kaggle passwords or API tokens in source code, the database, logs, or dashboard fields. Credentials must be provisioned out-of-band into the server's secret store and scoped/revocable where Kaggle supports it.

## Current status

- Platform selected for initial evaluation: Kaggle.
- Public official CLI/API documentation verified.
- No Kaggle account connected.
- No owner acceptance of platform or competition rules recorded.
- No competition selected or independently checked.
- No written competition-specific permission for autonomous submission recorded.
- No Kaggle adapter enabled; real submissions remain blocked.

The next activation step is owner-led: sign in to Kaggle in the browser, review and accept the rules for a chosen competition, then provide its public competition URL and confirm the country of residence to use for eligibility review. Never send account passwords or API tokens in chat.
