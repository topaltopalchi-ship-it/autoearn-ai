# Private credential vault

The vault is a local-only encrypted storage primitive for the single owner. It is
not yet wired into dashboard/API routes or provider integrations.

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

This storage module is not yet exposed through the UI or HTTP API. The app
currently has no login system; keep it bound to 127.0.0.1 and do not expose it
through a public host, LAN, or tunnel. Do not enter production credentials until
the API/UI integration, local access controls, backup/restore, and security
review are complete. Never store seed phrases or private wallet keys unless a
specific integration requires them and its security model has been reviewed.
