"""Encrypted local credential storage for the single-owner AutoEarn workspace.

Secrets are encrypted at rest with AES-256-GCM. A passphrase-derived key is
computed with scrypt for every operation and is never persisted.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

ROOT = Path(__file__).resolve().parent.parent
VAULT_DB = Path(os.getenv("AUTOEARN_VAULT_DB", ROOT / "data" / "autoearn-vault.db"))
SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
MAX_SECRET_BYTES = 8192


class VaultError(ValueError):
    """Base class for safe-to-display vault validation errors."""


class InvalidPassphrase(VaultError):
    """The passphrase cannot decrypt the requested credential."""


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    if not isinstance(passphrase, str) or len(passphrase) < 14:
        raise VaultError("عبارت اصلی باید حداقل ۱۴ نویسه داشته باشد.")
    if len(passphrase.encode("utf-8")) > 1024:
        raise VaultError("عبارت اصلی بیش از حد طولانی است.")
    return Scrypt(salt=salt, length=KEY_BYTES, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P).derive(
        passphrase.encode("utf-8")
    )


def _connect() -> sqlite3.Connection:
    VAULT_DB.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(VAULT_DB.parent, 0o700)
    except OSError:
        pass
    db = sqlite3.connect(VAULT_DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA secure_delete = ON")
    return db


def _init_db() -> None:
    with _connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                provider TEXT NOT NULL,
                credential_type TEXT NOT NULL,
                salt BLOB NOT NULL,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
    try:
        os.chmod(VAULT_DB, 0o600)
    except OSError:
        pass


def _aad(row_id: int, label: str, provider: str, credential_type: str) -> bytes:
    return f"autoearn-vault:v1:{row_id}:{label}:{provider}:{credential_type}".encode("utf-8")


def _metadata(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label": row["label"],
        "provider": row["provider"],
        "credential_type": row["credential_type"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "secret_configured": True,
    }


def list_credentials() -> list[dict[str, Any]]:
    """Return metadata only. Secret material is never included."""
    _init_db()
    with _connect() as db:
        rows = db.execute(
            "SELECT id, label, provider, credential_type, created_at, updated_at "
            "FROM credentials ORDER BY provider, label, id"
        ).fetchall()
    return [dict(row) | {"secret_configured": True} for row in rows]


def add_credential(
    *, label: str, provider: str, credential_type: str, secret: str, passphrase: str
) -> dict[str, Any]:
    label, provider, credential_type = label.strip(), provider.strip(), credential_type.strip()
    if not label or len(label) > 80 or not provider or len(provider) > 80:
        raise VaultError("نام کلید و سرویس باید بین ۱ تا ۸۰ نویسه باشد.")
    if credential_type not in {"api_key", "access_token", "signing_key", "account_secret"}:
        raise VaultError("نوع اطلاعات محرمانه معتبر نیست.")
    if not isinstance(secret, str) or not secret or len(secret.encode("utf-8")) > MAX_SECRET_BYTES:
        raise VaultError("مقدار محرمانه خالی یا بیش از حد بزرگ است.")

    _init_db()
    salt, nonce = secrets.token_bytes(SALT_BYTES), secrets.token_bytes(NONCE_BYTES)
    key = _derive_key(passphrase, salt)
    created = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        cursor = db.execute(
            "INSERT INTO credentials "
            "(label, provider, credential_type, salt, nonce, ciphertext, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (label, provider, credential_type, salt, nonce, b"", created, created),
        )
        row_id = int(cursor.lastrowid)
        ciphertext = AESGCM(key).encrypt(
            nonce, secret.encode("utf-8"), _aad(row_id, label, provider, credential_type)
        )
        db.execute("UPDATE credentials SET ciphertext = ? WHERE id = ?", (ciphertext, row_id))
        row = db.execute("SELECT * FROM credentials WHERE id = ?", (row_id,)).fetchone()
    try:
        os.chmod(VAULT_DB, 0o600)
    except OSError:
        pass
    return _metadata(row)


def get_secret(credential_id: int, passphrase: str) -> str:
    """Internal integration API. Do not expose this result through HTTP responses."""
    _init_db()
    with _connect() as db:
        row = db.execute("SELECT * FROM credentials WHERE id = ?", (credential_id,)).fetchone()
    if row is None:
        raise KeyError("credential not found")
    try:
        key = _derive_key(passphrase, row["salt"])
        plaintext = AESGCM(key).decrypt(
            row["nonce"],
            row["ciphertext"],
            _aad(row["id"], row["label"], row["provider"], row["credential_type"]),
        )
        return plaintext.decode("utf-8")
    except (InvalidTag, UnicodeDecodeError) as exc:
        raise InvalidPassphrase("عبارت اصلی نادرست است یا داده مخدوش شده است.") from exc


def delete_credential(credential_id: int, passphrase: str) -> None:
    """Verify the passphrase before deleting a stored credential."""
    get_secret(credential_id, passphrase)
    with _connect() as db:
        db.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))


def update_credential(
    credential_id: int, *, secret: str, passphrase: str
) -> dict[str, Any]:
    """Replace a secret without changing its public metadata."""
    current = get_secret(credential_id, passphrase)
    del current  # Do not retain the previous secret beyond verification.
    if not isinstance(secret, str) or not secret or len(secret.encode("utf-8")) > MAX_SECRET_BYTES:
        raise VaultError("مقدار محرمانه خالی یا بیش از حد بزرگ است.")
    with _connect() as db:
        row = db.execute("SELECT * FROM credentials WHERE id = ?", (credential_id,)).fetchone()
        if row is None:
            raise KeyError("credential not found")
        salt, nonce = secrets.token_bytes(SALT_BYTES), secrets.token_bytes(NONCE_BYTES)
        key = _derive_key(passphrase, salt)
        ciphertext = AESGCM(key).encrypt(
            nonce, secret.encode("utf-8"),
            _aad(row["id"], row["label"], row["provider"], row["credential_type"]),
        )
        updated = datetime.now(timezone.utc).isoformat()
        db.execute(
            "UPDATE credentials SET salt = ?, nonce = ?, ciphertext = ?, updated_at = ? WHERE id = ?",
            (salt, nonce, ciphertext, updated, credential_id),
        )
        saved = db.execute("SELECT * FROM credentials WHERE id = ?", (credential_id,)).fetchone()
    return _metadata(saved)
