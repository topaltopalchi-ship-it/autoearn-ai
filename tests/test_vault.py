import pytest

from app import vault


@pytest.fixture
def isolated_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault, "VAULT_DB", tmp_path / "private" / "vault.db")
    return vault


def test_secret_is_encrypted_at_rest_and_metadata_never_contains_secret(isolated_vault):
    secret = "sk-live-never-store-this-in-plaintext"
    saved = isolated_vault.add_credential(
        label="OpenAI primary", provider="openai", credential_type="api_key",
        secret=secret, passphrase="a-long-private-master-passphrase",
    )
    assert "secret" not in saved
    assert secret not in str(saved)
    raw = isolated_vault.VAULT_DB.read_bytes()
    assert secret.encode() not in raw
    assert isolated_vault.get_secret(saved["id"], "a-long-private-master-passphrase") == secret


def test_wrong_passphrase_does_not_return_secret(isolated_vault):
    saved = isolated_vault.add_credential(
        label="Search", provider="search", credential_type="api_key",
        secret="search-secret", passphrase="correct-master-passphrase",
    )
    with pytest.raises(isolated_vault.InvalidPassphrase):
        isolated_vault.get_secret(saved["id"], "incorrect-master-passphrase")


def test_list_returns_metadata_only(isolated_vault):
    isolated_vault.add_credential(
        label="Wallet signing", provider="wallet", credential_type="signing_key",
        secret="private-signing-material", passphrase="long-enough-master-passphrase",
    )
    rows = isolated_vault.list_credentials()
    assert len(rows) == 1
    assert rows[0]["credential_type"] == "signing_key"
    assert "secret" not in rows[0]


def test_update_rotates_ciphertext_and_keeps_metadata(isolated_vault):
    saved = isolated_vault.add_credential(
        label="Provider", provider="example", credential_type="access_token",
        secret="old-token", passphrase="master-passphrase-long",
    )
    updated = isolated_vault.update_credential(
        saved["id"], secret="new-token", passphrase="master-passphrase-long"
    )
    assert updated["id"] == saved["id"]
    assert isolated_vault.get_secret(saved["id"], "master-passphrase-long") == "new-token"


def test_delete_requires_correct_passphrase(isolated_vault):
    saved = isolated_vault.add_credential(
        label="Account", provider="site", credential_type="account_secret",
        secret="password-value", passphrase="master-passphrase-long",
    )
    with pytest.raises(isolated_vault.InvalidPassphrase):
        isolated_vault.delete_credential(saved["id"], "wrong-passphrase")
    assert len(isolated_vault.list_credentials()) == 1
    isolated_vault.delete_credential(saved["id"], "master-passphrase-long")
    assert isolated_vault.list_credentials() == []


def test_rejects_short_passphrases_and_unknown_credential_types(isolated_vault):
    with pytest.raises(isolated_vault.VaultError):
        isolated_vault.add_credential(
            label="Bad", provider="x", credential_type="api_key",
            secret="value", passphrase="short",
        )
    with pytest.raises(isolated_vault.VaultError):
        isolated_vault.add_credential(
            label="Bad", provider="x", credential_type="password",
            secret="value", passphrase="a-valid-long-master-passphrase",
        )
