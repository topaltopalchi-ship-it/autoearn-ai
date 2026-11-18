# Game integration implementation status

This document records the first live-code integration slice. It is deliberately read-only.

## Connected through documented public APIs

- **Lichess**: read-only Arena tournament discovery via `GET https://lichess.org/api/tournament`.
- **Chess.com**: read-only tournament detail lookup via `GET https://api.chess.com/pub/tournament/{url-ID}`.

Both endpoints are owner-authenticated inside AutoEarn. Requests use HTTPS with certificate verification, fixed provider hostnames, a bounded response body, a timeout, serialized request execution, and a fixed User-Agent. Redirects are not followed. No third-party URL is accepted as a fetch target.

Every returned event is labelled with:
- country: Iran;
- eligibility: unknown until event-specific official rules are reviewed;
- payout readiness: unknown;
- participation mode: manual review only;
- review required: true.

These metadata feeds do not automatically join events, send moves, create accounts, submit entries, or claim rewards. The platform catalog explicitly reports participation as disabled.

## API routes

- `GET /api/games/platforms`
- `GET /api/games/lichess/tournaments`
- `GET /api/games/chesscom/tournaments/{tournament_id}`

All routes require the AutoEarn owner credential. The Chess.com route takes a tournament URL identifier, not an arbitrary URL.

## Known limitations

- Chess.com PubAPI does not provide a universal search endpoint for every open event; the initial integration retrieves a known public tournament by its URL identifier.
- Lichess and Chess.com public APIs do not establish that an event accepts an Iran-resident participant or that prizes can lawfully be paid to that participant. Such checks remain separate and fail closed.
- The integrations are not account-linked. They use public metadata only and require no platform credentials.
- No claim is made that all games worldwide have been integrated. Additional platforms require their own official API and terms review.
