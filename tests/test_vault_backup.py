import pytest

from app import vault
from app.vault_backup import InvalidBackup, create_backup, restore_backup


PASSPHRASE = "a-strong-vault-backup-passphrase"


def make_vault(path):
    vault.VAULT_DB = path
    return vault.add_credential(
        label="OpenAI", provider="openai", credential_type="api_key",
        secret="test-secret-never-plaintext", passphrase=PASSPHRASE,
    )


def test_backup_is_encrypted_and_restore_recovers_credentials(tmp_path, monkeypatch):
    source = tmp_path / "source" / "vault.db"
    monkeypatch.setattr(vault, "VAULT_DB", source)
    saved = make_vault(source)
    backup = create_backup(source, tmp_path / "backup.aev", PASSPHRASE)
    assert b"test-secret-never-plaintext" not in backup.read_bytes()

    restored = tmp_path / "restored" / "vault.db"
    restore_backup(backup, restored, PASSPHRASE)
    monkeypatch.setattr(vault, "VAULT_DB", restored)
    assert vault.get_secret(saved["id"], PASSPHRASE) == "test-secret-never-plaintext"


def test_restore_rejects_wrong_passphrase_without_creating_destination(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    monkeypatch.setattr(vault, "VAULT_DB", source)
    make_vault(source)
    backup = create_backup(source, tmp_path / "backup.aev", PASSPHRASE)
    destination = tmp_path / "restored.db"
    with pytest.raises(InvalidBackup):
        restore_backup(backup, destination, "wrong-backup-passphrase")
    assert not destination.exists()


def test_restore_refuses_overwrite_by_default(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    monkeypatch.setattr(vault, "VAULT_DB", source)
    make_vault(source)
    backup = create_backup(source, tmp_path / "backup.aev", PASSPHRASE)
    destination = tmp_path / "existing.db"
    destination.write_bytes(b"do-not-overwrite")
    with pytest.raises(FileExistsError):
        restore_backup(backup, destination, PASSPHRASE)
    assert destination.read_bytes() == b"do-not-overwrite"


def test_restore_rejects_tampered_backup(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    monkeypatch.setattr(vault, "VAULT_DB", source)
    make_vault(source)
    backup = create_backup(source, tmp_path / "backup.aev", PASSPHRASE)
    damaged = tmp_path / "damaged.aev"
    raw = bytearray(backup.read_bytes())
    raw[-1] ^= 1
    damaged.write_bytes(raw)
    with pytest.raises(InvalidBackup):
        restore_backup(damaged, tmp_path / "restored.db", PASSPHRASE)
