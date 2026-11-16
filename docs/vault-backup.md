# Encrypted offline vault backup and restore

The optional Python backup helper creates an authenticated, encrypted snapshot
of the credential-vault SQLite database. Credential rows are already encrypted
individually with AES-256-GCM; the complete SQLite snapshot is wrapped in a
second AES-256-GCM layer using a separate random salt and nonce.

## Create a backup

```python
from app.vault import VAULT_DB
from app.vault_backup import create_backup

create_backup(VAULT_DB, "private-backups/autoearn-vault.aev", "your-long-backup-passphrase")
```

By default, creating a backup refuses to replace an existing destination. Set
`overwrite=True` only when you intentionally want to replace that backup.

## Restore a backup

```python
from app.vault import VAULT_DB
from app.vault_backup import restore_backup

restore_backup(
    "private-backups/autoearn-vault.aev",
    VAULT_DB,
    "your-long-backup-passphrase",
    overwrite=True,  # explicit because this replaces the current vault database
)
```

## Safety rules

- Use a strong backup passphrase (at least 14 characters) and store it separately
  from the backup file, preferably offline.
- The backup file is encrypted; never commit it to Git or upload it to a public
  storage location.
- Restore validates the outer authentication tag, SQLite integrity, schema,
  and every credential's inner AES-GCM tag before replacing a destination.
- Backup and restore refuse to overwrite existing files unless `overwrite=True`.
  Both operations stage the output in the destination directory and use
  no-clobber hard-link creation by default; explicit replacement uses atomic
  rename.
- Restore rejects files above the configured size limit before reading them.
- Keep the application stopped while restoring so it cannot write to the vault
  during replacement.
- This helper backs up the credential vault only. It does not back up the
  opportunity/task/reward database or application configuration.
- Loss of the backup passphrase makes the backup unrecoverable.
- The helper is a local Python API, not yet exposed as a dashboard upload or
  download route. Do not use production secrets until a separate security
  review and a real recovery drill have been completed.
