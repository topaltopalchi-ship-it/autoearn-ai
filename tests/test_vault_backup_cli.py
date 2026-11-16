from pathlib import Path

import pytest

from scripts import vault_backup_cli as cli


def test_create_command_reads_confirmed_passphrase_interactively(tmp_path, monkeypatch):
    source = tmp_path / "vault.db"
    destination = tmp_path / "backup.aev"
    seen = {}

    monkeypatch.setattr(cli, "_passphrase", lambda *, confirm=False: "a-strong-backup-passphrase")
    monkeypatch.setattr(
        cli,
        "create_backup",
        lambda src, dst, phrase, **kwargs: seen.update(
            source=src, destination=dst, passphrase=phrase, options=kwargs
        ) or Path(dst),
    )

    assert cli.main(["create", str(destination), "--source", str(source)]) == 0
    assert seen["passphrase"] == "a-strong-backup-passphrase"
    assert seen["options"] == {"overwrite": False}


def test_restore_existing_destination_requires_explicit_confirmation(tmp_path, monkeypatch):
    backup = tmp_path / "backup.aev"
    destination = tmp_path / "vault.db"
    backup.write_bytes(b"backup")
    destination.write_bytes(b"preserve-me")
    monkeypatch.setattr(cli, "_passphrase", lambda **kwargs: pytest.fail("must not ask passphrase"))
    monkeypatch.setattr(cli, "restore_backup", lambda *args, **kwargs: pytest.fail("must not restore"))

    assert cli.main(["restore", str(backup), str(destination)]) == 2
    assert destination.read_bytes() == b"preserve-me"


def test_cli_does_not_accept_passphrase_as_argument():
    with pytest.raises(SystemExit):
        cli.main(["create", "backup.aev", "secret-passphrase"])
