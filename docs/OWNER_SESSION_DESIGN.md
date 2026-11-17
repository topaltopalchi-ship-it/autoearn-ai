# Owner identity and browser-session design proposal

Status: **design proposal only — not implemented or approved for production**.

AutoEarn currently uses one shared owner token in a request header. The browser stores that token in `sessionStorage`. This is acceptable only for the current local-first, single-owner development workflow; it is not a production identity/session system. Do not expose the current service to the public internet.

## Security goals

- Authenticate one explicitly provisioned owner without embedding credentials in frontend assets.
- Keep browser credentials out of JavaScript-readable storage.
- Support explicit logout, server-side revocation, idle expiry, and absolute expiry.
- Prevent session fixation and cross-site request forgery.
- Fail closed when the session store or signing/key material is unavailable.
- Preserve an auditable record of security-relevant identity events without logging credentials or session identifiers.

## Proposed deployment model

For a single-owner deployment, prefer a local owner account provisioned through a one-time administrative CLI command. Store only a modern password hash (Argon2id through a maintained, pinned library with parameters reviewed for the target host); never store or log the password. Require a high-entropy password and provide no public self-service registration. Recovery should be an offline administrative reset that revokes every active session and records an audit event. The owner must explicitly choose and document this recovery model before implementation.

An independently managed OIDC identity provider is a valid alternative when the deployment has a stable provider and issuer. If selected, use Authorization Code with PKCE, exact issuer/audience/redirect URI validation, state and nonce validation, and no implicit flow. Do not mix an incomplete OIDC flow with the local-password proposal.

## Session lifecycle (proposed defaults; require review)

1. After successful authentication, generate at least 256 bits of cryptographically secure random session material.
2. Store only a keyed digest of the opaque session identifier in SQLite; use a dedicated session-pepper secret, separate from the owner password and other application secrets.
3. Issue the opaque identifier only in a cookie with `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, and a bounded `Max-Age`. Never put it in a URL, localStorage, sessionStorage, or logs. Set `Secure` unconditionally in production; local HTTP development needs an explicitly separate configuration.
4. Rotate the session identifier after login and any privilege/security boundary change. Reject the pre-authentication identifier after rotation.
5. Enforce both a 30-minute idle timeout and a 12-hour absolute lifetime as initial review values. Update last activity transactionally and do not extend the absolute expiry.
6. Logout revokes the server-side record and expires the cookie. Password reset, credential rotation, and administrative recovery revoke all sessions.
7. Validate the session on every owner-protected request. Missing, expired, revoked, malformed, or unverifiable sessions fail closed.

These timeout values are proposals, not user-approved policy. Review usability, threat model, and operational requirements before implementation.

## CSRF and browser request controls

- Use a synchronizer CSRF token bound to the authenticated server-side session. Return it only to the authenticated same-origin application and require it in a custom header for every state-changing browser request.
- Verify the request Origin against a configured canonical external origin for state-changing requests. Reject absent or mismatched Origin on browser-cookie-authenticated mutations; define a separate, explicit policy for non-browser administrative clients.
- Keep `SameSite=Lax` as defense in depth, not as the only CSRF control.
- Keep the existing same-origin middleware, but configure canonical origin and trusted proxy behavior explicitly. Never trust arbitrary forwarded headers.
- Rotate CSRF material with the session and reject tokens from a previous session.

## Abuse controls and audit

- Retain persistent authentication throttling, but key identifiers with a dedicated server-side HMAC key rather than storing raw addresses. Consider separate per-account and per-source budgets to reduce distributed guessing and avoid a single shared-IP lockout.
- Do not reveal whether an account exists or whether a password was close to correct.
- Audit login success/failure, logout, session revocation, password reset, and recovery with timestamp and outcome only. Redact passwords, cookies, CSRF tokens, bearer values, and raw request headers.
- Database failures, clock anomalies, and key-material failures must fail closed for owner operations.

## Implementation and acceptance sequence

- [ ] Confirm the identity model: local owner password or a named OIDC provider.
- [ ] Confirm bootstrap and offline recovery procedures.
- [ ] Approve idle/absolute expiry values and canonical deployment origin.
- [ ] Add schema migration for sessions, revocation, and security audit events.
- [ ] Implement credential verification using a reviewed password-hashing library, or the selected OIDC flow.
- [ ] Implement opaque server-side sessions, cookie flags, rotation, expiry, and revocation.
- [ ] Implement session-bound CSRF tokens and explicit trusted-proxy/origin configuration.
- [ ] Replace every owner-token dependency consistently in API routes and frontend code; remove the legacy token only after migration tests pass.
- [ ] Test fixation, replay, expiry, logout/revocation, CSRF, origin mismatch, malformed cookies, database outage, key loss, and concurrent requests.
- [ ] Complete independent security review before any public deployment.

## Non-goals and current limitations

This document does not implement authentication, issue cookies, create accounts, change the current owner-token flow, or authorize public deployment. The existing owner token and `sessionStorage` behavior remain in place until a reviewed implementation is completed. The production deployment checklist remains blocking.
