# AutoEarn AI

A transparent opportunity discovery and reward-tracking workspace.

The first release is a local-first MVP. It helps users record opportunity metadata, compare opportunities with an explainable score, and track their own progress. It does not promise income or automate clicks, gameplay, spam, account creation, or platform activity.

## Current implementation

- HTTP(S)-only URL validation and canonicalization for duplicate detection.
- Removal of common tracking query parameters and URL fragments.
- Opportunity metadata validation.
- Explainable 0–100 scoring using reward clarity, terms clarity, source trust, region fit, and effort fit.
- Unit tests using Python's standard library.
- GitHub Actions workflow to run unit tests on pushes and pull requests.

## Development

Requires Python 3.10 or newer.

Run the tests:

```bash
python -m unittest discover -s tests -v
```

## Scoring notes

The score is a heuristic based only on metadata supplied to the application. It is not proof that a platform is legitimate or that a reward will be paid. Users must verify eligibility, regional restrictions, and platform terms before participating.

## Safety boundaries

AutoEarn AI is an assisted decision-support tool. Website discovery and analysis must respect site terms, robots policies, privacy, and applicable law. The product will not automate gameplay, clicks, ad views, referrals, spam, or other activity intended to manipulate reward systems.

## Automation policy and giveaway classification

Each opportunity can record its automation policy (allowed, prohibited, or unknown), CAPTCHA requirement, opportunity category, and the source/evidence used for review. Unknown policy or CAPTCHA status is treated as manual-only. A site that prohibits automation is excluded from automation eligibility. CAPTCHA-protected opportunities are never marked auto-eligible.

Free giveaways and skill contests may be marked auto-eligible only when automation is explicitly recorded as allowed, CAPTCHA is explicitly recorded as absent, a non-unknown evidence source is selected, and a supporting evidence URL or reviewer note is supplied. Evidence is still user-provided and must be checked by a person; the application does not independently verify that a website's terms permit automation. Paid lotteries and betting remain manual-only and are not automated. These labels are not legal advice or proof of eligibility, and prizes are not guaranteed income.

The policy classifier does not browse, submit forms, place bets, pay entry fees, solve CAPTCHAs, or bypass robots/anti-bot controls. Missing or uncertain evidence fails closed.

## Maximum-compliant autonomy mode

The automation orchestrator prepares internal review work automatically for opportunities that pass the explicit policy gate. The preparation endpoint is idempotent and creates at most one active/completed internal-review task per eligible opportunity:

- `POST /api/automation/prepare` queues internal metadata-review tasks only for opportunities classified as `auto`.
- `GET /api/automation/status` reports eligible/manual/excluded counts and task states.
- Tasks of type `internal_review` are marked `auto_queued`; this is preparation, not a claim that a third-party action has been executed.
- Site participation, reward claims, account actions, and unspecified actions remain `pending_approval` and cannot be completed before explicit approval.
- The policy gate fails closed. Even an `auto` label is based on recorded evidence and is not independent legal verification or a guarantee that a provider supports automation.

No automated ad watching, gameplay, clicking, CAPTCHA solving/bypass, anti-bot evasion, account creation, betting, payment, or third-party form submission is enabled. Human presence and approval remain required wherever platform rules or the nature of the action demand them.

## Local skill-game engines

The game modules analyze puzzle states supplied to the local application. They do not log into, control, click, or submit answers to third-party websites.

- `POST /api/games/solve`: exact-arithmetic number-target solver. The associated opportunity must pass the explicit skill-contest policy gate.
- `GET /api/games/stats`: local puzzle attempts and solve rate.
- `GET /api/games/benchmark`: deterministic arithmetic benchmark; optional `rounds` parameter is bounded by the API.
- `GET /api/games/practice`: bounded offline number-puzzle practice.
- `GET /api/games/memory-practice`: bounded offline memory-sequence practice.
- `POST /api/games/word/filter`: Wordle-style candidate filtering using supplied feedback.
- `POST /api/games/logic/mastermind`: bounded Mastermind-style deduction from supplied guesses.
- `POST /api/games/strategy/recommend`: UCB1 strategy recommendation using supplied local history or saved observations for one game type.
- `POST /api/games/strategy/observe`: persist one local-practice observation (reward 0–1 and optional duration).
- `GET /api/games/strategy/stats`: summarize persisted local observations, optionally filtered by game type.
- `GET /api/player/status`: report local attempts, saved observations, policy-review counts, and manually recorded paid rewards.

### Strategy learning data

Strategy observations are stored in the application's SQLite database in `strategy_observations`. Each observation is scoped to a `game_type`, strategy name, bounded reward, optional duration, and timestamp. Recommendations only load observations for the requested game type, preventing number-game history from influencing word- or logic-game recommendations.

For a local training loop:

1. Run a local practice/solver session.
2. Record the outcome with `POST /api/games/strategy/observe`.
3. Request a recommendation with `POST /api/games/strategy/recommend`, supplying `game_type` and candidate strategy names.
4. Inspect aggregate local results with `GET /api/games/strategy/stats`.

A UCB1 recommendation is a way to choose which local strategy to test next; it is not a trained general-purpose AI model and does not predict cash-prize wins. The player-status endpoint deliberately reports `real_world_win_rate: null`, `external_gameplay_enabled: false`, and `automated_payment_enabled: false` until separately authorized integrations and appropriate validation exist.

### Example strategy observation

```json
{
  "game_type": "number",
  "strategy": "exact_search",
  "reward": 1.0,
  "duration_ms": 42
}
```

### Example strategy recommendation

```json
{
  "game_type": "number",
  "candidates": ["exact_search", "heuristic_search"],
  "exploration": 1.4
}
```

## External platform integrations

No external gameplay, entry submission, prize claiming, payment, or withdrawal automation is implemented. A future adapter must use an official/authorized interface and be reviewed against the specific platform's current terms before any external action. Permission must be explicit, evidence must be reviewed by a person, and unknown or changed rules must stop execution. CAPTCHA solving/bypass, anti-bot evasion, wagering, and paid lottery participation are out of scope.

Local solver accuracy, practice solve rate, and UCB1 scores are not third-party competition win rates or earnings forecasts. No prize or income is guaranteed.
