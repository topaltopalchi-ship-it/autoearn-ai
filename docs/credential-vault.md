# Private credential vault

The vault is a local-only encrypted store for the single owner, integrated with authenticated API routes and a Persian dashboard form. Provider integrations are not enabled yet.

## Security model

- Secrets are encrypted at rest with AES-256-GCM.
- A key is derived per operation from the owner's passphrase using scrypt
  (N=2^14, r=8, p=1); the passphrase and derived key are never persisted.
- Each record has a random 16-byte salt and 12-byte nonce. Metadata is
  authenticated as AES-GCM additional authenticated data.
- The SQLite file is created with restrictive permissions where supported
  (directory 0700, file 0600). These permissions are best-effort on platforms
  that do not implement POSIX modes.
- Listing returns metadata only. Secret retrieval is an internal Python API;
  never serialize its return value into dashboard responses or logs.
- A lost passphrase means the encrypted secrets cannot be recovered. Keep an
  offline backup of the vault file and passphrase separately.

## Supported record types

- `api_key`: AI and search provider API keys
- `access_token`: provider access tokens
- `signing_key`: signing material (only where the platform explicitly supports it)
- `account_secret`: account passwords or recovery secrets

## Important limitations before use

The dashboard can add credentials and list metadata; it never returns secret material. The API supports metadata listing, encrypted creation/update, and passphrase-verified deletion. Each write request carries the vault passphrase and the browser does not persist it. Do not enter production credentials until backup/restore and an independent security review are complete. Provider API calls are not wired to retrieve or use stored credentials yet. Never store seed phrases or private wallet keys unless a
specific integration requires them and its security model has been reviewed.


## Network boundary

The ASGI application itself rejects requests when the TCP peer address is not
a loopback IP address, even if the server is accidentally started on
0.0.0.0 or a LAN interface. This is a defense-in-depth boundary, not user
authentication: local processes running under the same operating-system user
can still access the app. Do not place the app behind a publicly reachable
reverse proxy or tunnel, and keep the local machine account protected.


## HTTP API and dashboard integration

- `GET /api/vault/credentials` returns metadata only.
- `POST /api/vault/credentials` encrypts and stores a credential.
- `PUT /api/vault/credentials/{id}` replaces a secret after passphrase verification.
- `DELETE /api/vault/credentials/{id}` verifies the passphrase before deletion.
- All vault routes are protected by the local owner session middleware.
- The UI clears the secret and passphrase fields after a successful save. Secret values are never rendered again.
- Keep the app bound to loopback. Loopback access is not a substitute for OS account security or protection from other local processes.

Provider integration is a separate milestone. No stored key is automatically sent to an external service by this change.
