# Zoa agent runtime (separate from the AutoEarn website)

This is an optional, isolated worker for the official Zoa Games agent starter. It is
not a Supabase Edge Function: the agent keeps a Socket.IO connection open while a
game is running, so it needs a persistent Node.js process. Netlify static hosting
and short-lived Supabase Edge Function invocations are not the right place to run it.

## What it does

- Uses the upstream Zoa starter at the pinned commit
  `4016552105862093699c5d20a6aff6255c86fc9c`.
- Connects to `https://play.zoagames.com` using the agent API key.
- Defaults to the free practice table only. It does not enter the competitive ladder
  unless you explicitly set `ZOA_MODE=ladder` in your local `.env` file.
- Uses only Zoa's non-purchasable score chips. It does not connect a wallet,
  deposit money, purchase chips, or withdraw funds.

## Human setup required

1. Create a Zoa account yourself at https://play.zoagames.com and verify the email.
2. In the lobby, generate an agent invite code.
3. Register the agent through Zoa's documented `POST /api/agent/register` flow.
   Zoa returns the agent API key once. Keep it private.
4. On an always-on machine or server with Docker Compose, copy `.env.example`
   to `.env` and put the key in `.env`.
5. Keep `ZOA_MODE=practice` for the first run. Start it with
   `docker compose up -d --build`.
6. Inspect output with `docker compose logs -f zoa-agent`; stop it with
   `docker compose down`.
7. Only if you deliberately choose to enter the ladder, change `ZOA_MODE=ladder`
   in your local `.env` and recreate the worker with
   `docker compose up -d --build --force-recreate`.

The key stays in the local `.env` file and is passed to the container as an
environment variable. It is not included in the Docker image, Git history, browser
JavaScript, or Supabase. Never paste it into a chat or commit it.

## Prize and eligibility warning

The upstream starter's current README describes Season 0 as free play with **no
prize pool**, and says a later season may be funded. A third-party directory has
reported a Season 1 prize pool, but that is not sufficient proof of a payable
prize. Before relying on any reward, check Zoa's current official rules at
https://play.zoagames.com/agent-docs for the live season, exact prize table,
eligibility, age, payout network, identity verification, and payment conditions.
No earnings are guaranteed. The platform pays any prize to the eligible human
owner, not to AutoEarn or the agent.

## Important boundaries

- The human creates the account, verifies email, generates the invite code, and
  registers the agent. This package does not automate signup or bypass checks.
- Do not link a wallet or fund an account for this integration.
- The game uses virtual chips as score. They are not money and must never be
  treated as a cash balance.
- The upstream documents a limit of 30 games per agent per day and one ladder
  agent per owner. Respect the current platform limits; do not run multiple agents
  to farm rankings or violate Zoa's rules.
- AutoEarn's website does not yet control, monitor, or store this worker's API
  key. This package is a separate runtime, not a completed in-app connection.

## Upstream

Source: https://github.com/intuitiontom/zoa-agent-starter  
Pinned commit: `4016552105862093699c5d20a6aff6255c86fc9c`  
License: MIT (upstream)
