from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from scripts.backup import create_backup
from scripts.restore import restore_backup


def test_backup_captures_sqlite_snapshot_and_private_evidence(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE earnings (id INTEGER PRIMARY KEY, amount INTEGER)")
        db.execute("INSERT INTO earnings(amount) VALUES (1250)")
        db.commit()

    evidence = tmp_path / "private_evidence"
    evidence.mkdir()
    receipt = evidence / "receipt.pdf"
    receipt.write_bytes(b"%PDF-1.7 private receipt")

    destination = tmp_path / "backups" / "snapshot"
    manifest = create_backup(database, evidence, destination)

    with sqlite3.connect(destination / "autoearn.db") as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT amount FROM earnings").fetchone()[0] == 1250

    copied_receipt = destination / "private_evidence" / "receipt.pdf"
    assert copied_receipt.read_bytes() == receipt.read_bytes()
    assert manifest["sqlite_integrity_check"] == "ok"
    assert manifest["evidence_files"][0]["sha256"] == hashlib.sha256(receipt.read_bytes()).hexdigest()
    stored_manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert stored_manifest["database_sha256"] == manifest["database_sha256"]


def test_backup_refuses_to_overwrite_existing_destination(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    destination = tmp_path / "backup"
    destination.mkdir()
    with pytest.raises(FileExistsError):
        create_backup(database, evidence, destination)


def test_backup_rejects_evidence_symlinks(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("do not follow")
    try:
        (evidence / "linked.txt").symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform")

    with pytest.raises(ValueError, match="symlinks"):
        create_backup(database, evidence, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()

def test_backup_files_are_owner_only_on_posix(tmp_path):
    import os
    import stat

    if os.name != "posix":
        pytest.skip("POSIX permission modes are not available")
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    destination = tmp_path / "backup"
    create_backup(database, evidence, destination)

    assert stat.S_IMODE((destination / "autoearn.db").stat().st_mode) == 0o600
    assert stat.S_IMODE((destination / "manifest.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((destination / "private_evidence").stat().st_mode) == 0o700


def test_restore_verifies_and_recovers_backup_without_overwriting(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE earnings (id INTEGER PRIMARY KEY, amount INTEGER)")
        db.execute("INSERT INTO earnings(amount) VALUES (875)")
    evidence = tmp_path / "private_evidence"
    evidence.mkdir()
    (evidence / "proof.png").write_bytes(b"\\x89PNG\\r\\n\\x1a\\nreceipt")
    backup = tmp_path / "backups" / "snapshot"
    create_backup(database, evidence, backup)

    destination = tmp_path / "recovered"
    manifest = restore_backup(backup, destination)
    with sqlite3.connect(destination / "autoearn.db") as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT amount FROM earnings").fetchone()[0] == 875
    assert (destination / "private_evidence" / "proof.png").read_bytes() == (evidence / "proof.png").read_bytes()
    assert manifest["sqlite_integrity_check"] == "ok"
    with pytest.raises(FileExistsError):
        restore_backup(backup, destination)


def test_restore_rejects_tampered_evidence_and_does_not_create_destination(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "receipt.pdf").write_bytes(b"%PDF-1.4 receipt")
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    (backup / "private_evidence" / "receipt.pdf").write_bytes(b"tampered")
    destination = tmp_path / "recovered"

    with pytest.raises(ValueError, match="checksum or size mismatch"):
        restore_backup(backup, destination)
    assert not destination.exists()
