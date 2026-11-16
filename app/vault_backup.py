"""Authenticated, passphrase-encrypted offline backups for the credential vault.

Backups contain the SQLite vault database (whose credential values are already
AES-GCM encrypted) wrapped in a second AES-256-GCM layer. Restore validates the
SQLite file and authenticates every credential before replacing a destination.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.vault import NONCE_BYTES, SALT_BYTES, VaultError, _aad, _derive_key

MAGIC = b"AUTOEARN-VAULT-BACKUP\\x01"
MAX_BACKUP_BYTES = 64 * 1024 * 1024
_REQUIRED_COLUMNS = {
    "id", "label", "provider", "credential_type",
    "salt", "nonce", "ciphertext", "created_at", "updated_at",
}


class InvalidBackup(VaultError):
    """Backup is invalid, corrupted, or encrypted with another passphrase."""


def _snapshot_database(source: Path) -> bytes:
    if not source.is_file():
        raise FileNotFoundError("Vault database does not exist.")
    src = sqlite3.connect(source)
    dst = sqlite3.connect(":memory:")
    try:
        src.backup(dst)
        result = dst.serialize()
    finally:
        dst.close()
        src.close()
    if len(result) > MAX_BACKUP_BYTES:
        raise VaultError("Vault backup exceeds the 64 MiB safety limit.")
    return result


def create_backup(
    source: str | Path, destination: str | Path, passphrase: str, *, overwrite: bool = False
) -> Path:
    """Create an encrypted backup; never replace an existing file by default."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise VaultError("Backup destination must differ from the vault database.")
    if destination.exists() and not overwrite:
        raise FileExistsError("Backup destination exists; pass overwrite=True to replace it.")
    plaintext = _snapshot_database(source)
    salt, nonce = secrets.token_bytes(SALT_BYTES), secrets.token_bytes(NONCE_BYTES)
    key = _derive_key(passphrase, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, MAGIC)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=".autoearn-backup-", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(MAGIC + salt + nonce + ciphertext)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o600)
        # Atomic hard-link creation provides no-clobber semantics on the same filesystem.
        if overwrite:
            os.replace(temporary_name, destination)
        else:
            os.link(temporary_name, destination)
            os.unlink(temporary_name)
        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
    return destination


def _validate_database(data: bytes, passphrase: str) -> None:
    db = sqlite3.connect(":memory:")
    try:
        db.deserialize(data)
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise InvalidBackup("Backup database integrity check failed.")
        columns = {row[1] for row in db.execute("PRAGMA table_info(credentials)")}
        if not _REQUIRED_COLUMNS.issubset(columns):
            raise InvalidBackup("Backup does not contain a compatible credential vault.")
        for row in db.execute(
            "SELECT id, label, provider, credential_type, salt, nonce, ciphertext FROM credentials"
        ):
            row_id, label, provider, kind, salt, nonce, ciphertext = row
            try:
                key = _derive_key(passphrase, salt)
                AESGCM(key).decrypt(nonce, ciphertext, _aad(row_id, label, provider, kind))
            except (InvalidTag, ValueError) as exc:
                raise InvalidBackup("Backup passphrase is incorrect or credential data is damaged.") from exc
    except sqlite3.DatabaseError as exc:
        raise InvalidBackup("Backup does not contain a valid SQLite database.") from exc
    finally:
        db.close()


def restore_backup(
    backup: str | Path, destination: str | Path, passphrase: str, *, overwrite: bool = False
) -> Path:
    """Validate fully, then atomically install the restored vault database."""
    backup, destination = Path(backup), Path(destination)
    if backup.resolve() == destination.resolve():
        raise VaultError("Backup and restore destination must differ.")
    if destination.exists() and not overwrite:
        raise FileExistsError("Restore destination exists; pass overwrite=True to replace it.")
    header_size = len(MAGIC) + SALT_BYTES + NONCE_BYTES
    maximum_file_size = MAX_BACKUP_BYTES + header_size + 16
    if not backup.is_file() or backup.stat().st_size <= header_size or backup.stat().st_size > maximum_file_size:
        raise InvalidBackup("Backup format or size is invalid.")
    raw = backup.read_bytes()
    if not raw.startswith(MAGIC):
        raise InvalidBackup("Backup format or size is invalid.")
    offset = len(MAGIC)
    salt, nonce = raw[offset:offset + SALT_BYTES], raw[offset + SALT_BYTES:header_size]
    try:
        plaintext = AESGCM(_derive_key(passphrase, salt)).decrypt(nonce, raw[header_size:], MAGIC)
    except (InvalidTag, ValueError) as exc:
        raise InvalidBackup("Backup passphrase is incorrect or backup is damaged.") from exc
    if len(plaintext) > MAX_BACKUP_BYTES:
        raise InvalidBackup("Restored database exceeds the 64 MiB safety limit.")
    _validate_database(plaintext, passphrase)

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=".autoearn-restore-", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(plaintext)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o600)
        check = sqlite3.connect(temporary_name)
        try:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise InvalidBackup("Staged restore failed integrity validation.")
        finally:
            check.close()
        if overwrite:
            os.replace(temporary_name, destination)
        else:
            os.link(temporary_name, destination)
            os.unlink(temporary_name)
        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
    return destination
