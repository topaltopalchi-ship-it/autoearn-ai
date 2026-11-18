# Game and esports platform integration plan

## Owner and jurisdiction boundary

AutoEarn is configured for one real owner resident in **Iran**. Do not use another person's account, address, identity, payment route, or country as a substitute. A platform/game is not marked eligible merely because its API is reachable. For every event, retain separate states for (1) country/residency eligibility, (2) account and age eligibility, (3) prize/payout availability, (4) game/platform terms, and (5) permission for any proposed automation. Unknown evidence blocks joining and submission.

## Integration levels

- **Discover (read-only):** fetch public game, tournament, championship, schedule, and rules metadata from a documented official API.
- **Prepare (assist):** summarize rules, deadlines, eligibility evidence, and a human-reviewed participation plan.
- **Participate (gated):** only an official documented API, explicit written/terms permission for the exact action, verified Iran eligibility and payout route, an approved adapter, and a fresh owner confirmation. No browser bots, gameplay bots, anti-cheat bypass, CAPTCHA solving, account creation, false identity, or automatic acceptance of terms.
- A read-only API is never treated as permission to join, play, submit, or claim a prize.

## Verified platform candidates

| Platform / ecosystem | Official capability evidenced | AutoEarn integration status | Boundary |
|---|---|---|---|
| Lichess | Public API documentation covers games, tournaments, puzzles, broadcasts, and other resources. Lichess explicitly recommends documented API use over scraping. | **First read-only candidate; not connected yet** | Use for tournament/event discovery and public game metadata. Do not automate player moves or play on the owner's behalf. Respect one-request-at-a-time guidance and wait 60 seconds after HTTP 429. |
| Chess.com | PubAPI exposes public player, game, club, and tournament data; it is read-only and cannot send moves or commands. | **Read-only candidate; not connected yet** | Discovery and public metadata only. No move submission or gameplay automation. |
| FACEIT | Official Data API exposes public game, championship, tournament, match, team, player, and statistics data; requires a developer app/API key. | **Candidate pending owner-created app key** | Start with server-side read-only data. Keep the key server-side. Data API access does not imply permission to enter or submit to a tournament. |
| Riot Games (League of Legends, Teamfight Tactics, and other supported titles) | Official developer portal offers game APIs. Personal keys are limited to personal projects/research; Tournament API access is not available with personal keys and production access requires registration/approval. | **Candidate pending product registration and key review** | Public stats/tournament metadata only where authorized. Do not automate gameplay, ranked play, or submissions. Respect per-game policies and required product registration. |
| Kaggle competitions (not a game publisher) | Official competition platform/API and CLI documentation are already tracked in the Kaggle onboarding plan. | **Adapter disabled; not connected** | Iran is excluded under the general competition terms reviewed for this project. Do not attempt entry through another person's account or a different country. |

## Expansion queue

The following are research targets, not approved integrations. Add them only after reviewing current official developer documentation, API access, regional terms, and payout rules:

- Toornament — tournament organizer/competition APIs.
- Start.gg — tournament discovery and event metadata API.
- Supercell titles — official developer APIs for supported titles, subject to API access and game-specific policies.
- Valve/Steam ecosystem — official Web API where it exposes relevant public metadata; Steam access alone is not proof of tournament-entry or reward support.
- Additional esports organizers and game publishers discovered through official developer portals.

Do not add an unofficial scraper or a third-party API mirror as an official integration.

## Implementation sequence

1. Add read-only adapters for Lichess and Chess.com using only documented public endpoints, bounded response sizes, strict HTTPS host allowlists, caching, provenance, and conservative rate limits.
2. Add a FACEIT adapter after the owner creates an app and configures a server-side key outside Git and the browser.
3. Add Riot metadata only after product registration and key permissions are confirmed; keep personal-key limitations explicit.
4. Expand the platform catalog only from verified official documentation. Keep each adapter disabled until its configuration and smoke tests pass.
5. Route every discovered event through the existing pending-review and country/payout eligibility pipeline. Discovery must never auto-join an event.
6. Keep all real submissions disabled by default. Enabling an adapter must not bypass the global emergency pause or the separate owner-confirmation gate.

## Required evidence before an event can be recommended as joinable

- Canonical event URL and official rules URL.
- Event-specific accepted countries/residency and age restrictions.
- Whether residents of Iran may enter, based on the actual event rules and applicable law.
- Prize form, currency, minimum threshold, payout provider, and whether a lawful usable payout route exists for this owner.
- Whether AI assistance and automated agents are permitted, with the exact allowed scope.
- Entry deadline, fees, skill/game requirements, and any team/member requirements.
- Timestamped official evidence and a human review decision.

If any required field is unknown, display the event as **needs review / not joinable**, not as an available earning opportunity.

## Official references

- Lichess API tips: https://lichess.org/page/api-tips
- Lichess API reference: https://lichess.org/api
- Chess.com PubAPI explanation and restrictions: https://support.chess.com/en/articles/9650547-what-is-the-pubapi-and-how-do-i-use-it
- FACEIT developer overview: https://docs.faceit.com/docs/
- FACEIT Data API: https://docs.faceit.com/docs/data-api/
- FACEIT API key handling: https://docs.faceit.com/getting-started/authentication/api-keys/
- Riot developer portal and key types: https://developer.riotgames.com/docs/portal
- Riot League of Legends API policy and tournament API: https://developer.riotgames.com/docs/lol
- Kaggle terms: https://www.kaggle.com/terms

## Current status

This document is an integration plan and verified capability inventory. It does **not** claim that any external account is linked, that API credentials have been configured, or that a game/event is eligible for an Iran-resident owner. Lichess and Chess.com are the lowest-friction read-only implementation candidates; FACEIT and Riot require owner-controlled developer setup.