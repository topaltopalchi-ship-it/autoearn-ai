from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from scripts.backup import create_backup
from scripts.restore import _reject_excessive_json_nesting, restore_backup


def test_backup_captures_sqlite_snapshot_and_private_evidence(tmp_path):
    database = tmp_path / "autoearn.db"
    evidence = tmp_path / "private_evidence"
    evidence.mkdir()
    receipt = evidence / "receipt.pdf"
    receipt_payload = b"%PDF-1.7 private receipt"
    receipt.write_bytes(receipt_payload)
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE earnings (id INTEGER PRIMARY KEY, amount INTEGER)")
        db.execute("INSERT INTO earnings(amount) VALUES (1250)")
        db.execute("""CREATE TABLE earnings_evidence (
            id INTEGER PRIMARY KEY, ledger_id INTEGER, stored_name TEXT,
            media_type TEXT, size_bytes INTEGER, sha256 TEXT, created_at TEXT
        )""")
        db.execute(
            "INSERT INTO earnings_evidence VALUES (1, 1, ?, 'application/pdf', ?, ?, '2026-01-01')",
            (receipt.name, len(receipt_payload), hashlib.sha256(receipt_payload).hexdigest()),
        )
        db.commit()

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



@pytest.mark.parametrize("database_name", ["manifest.json", "PRIVATE_EVIDENCE"])
def test_backup_rejects_database_name_colliding_with_reserved_backup_entry(tmp_path, database_name):
    database = tmp_path / database_name
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    destination = tmp_path / "backup"

    with pytest.raises(ValueError, match="reserved backup entry"):
        create_backup(database, evidence, destination)
    assert not destination.exists()


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


def test_backup_rejects_symlinked_evidence_directory(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    real_evidence = tmp_path / "real-evidence"
    real_evidence.mkdir()
    linked_evidence = tmp_path / "linked-evidence"
    try:
        linked_evidence.symlink_to(real_evidence, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform")

    with pytest.raises(ValueError, match="Symbolic links"):
        create_backup(database, linked_evidence, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()


def test_backup_rejects_symlinked_database_file(tmp_path):
    real_database = tmp_path / "real.db"
    with sqlite3.connect(real_database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    linked_database = tmp_path / "linked.db"
    try:
        linked_database.symlink_to(real_database)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform")
    evidence = tmp_path / "evidence"
    evidence.mkdir()

    with pytest.raises(ValueError, match="Symbolic links"):
        create_backup(linked_database, evidence, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()


def test_backup_rejects_symlinked_destination_parent(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    try:
        linked_parent.symlink_to(real_parent, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform")

    with pytest.raises(ValueError, match="Symbolic links"):
        create_backup(database, evidence, linked_parent / "backup")
    assert not (real_parent / "backup").exists()


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
    (evidence / "proof.png").write_bytes(b"\x89PNG\r\n\x1a\nreceipt")
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



def test_restore_rejects_destination_inside_backup_directory(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    destination = backup / "nested" / "recovered"

    with pytest.raises(ValueError, match="outside the backup directory"):
        restore_backup(backup, destination)
    assert not destination.exists()


@pytest.mark.parametrize("database_name", ["manifest.json", "PRIVATE_EVIDENCE"])
def test_restore_rejects_database_name_colliding_with_reserved_backup_entry(tmp_path, database_name):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["database_file"] = database_name
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    destination = tmp_path / "recovered"

    with pytest.raises(ValueError, match="Invalid database filename"):
        restore_backup(backup, destination)
    assert not destination.exists()


def test_restore_rejects_symlinked_backup_directory(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    linked_backup = tmp_path / "linked-backup"
    try:
        linked_backup.symlink_to(backup, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform")

    with pytest.raises(ValueError, match="Symbolic links"):
        restore_backup(linked_backup, tmp_path / "recovered")
    assert not (tmp_path / "recovered").exists()


def test_restore_rejects_symlinked_destination_parent(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    try:
        linked_parent.symlink_to(real_parent, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform")

    with pytest.raises(ValueError, match="Symbolic links"):
        restore_backup(backup, linked_parent / "recovered")
    assert not (real_parent / "recovered").exists()


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


def test_backup_fails_when_sqlite_references_missing_receipt(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("""CREATE TABLE earnings_evidence (
            id INTEGER PRIMARY KEY, ledger_id INTEGER, stored_name TEXT,
            media_type TEXT, size_bytes INTEGER, sha256 TEXT, created_at TEXT
        )""")
        db.execute(
            "INSERT INTO earnings_evidence VALUES (1, 1, 'missing.pdf', 'application/pdf', 5, 'deadbeef', '2026-01-01')"
        )
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    destination = tmp_path / "backup"

    with pytest.raises(RuntimeError, match="stop the app and retry"):
        create_backup(database, evidence, destination)
    assert not destination.exists()


@pytest.mark.parametrize("manifest_payload", [
    "[]",
    "{",
    '{"format_version": true, "sqlite_integrity_check": "ok"}',
    '{"format_version": 1, "sqlite_integrity_check": "ok", "database_size_bytes": true, "database_sha256": "bad"}',
])
def test_restore_rejects_malformed_manifest_without_creating_destination(tmp_path, manifest_payload):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    (backup / "manifest.json").write_text(manifest_payload, encoding="utf-8")
    destination = tmp_path / "recovered"

    with pytest.raises(ValueError):
        restore_backup(backup, destination)
    assert not destination.exists()


def test_restore_rejects_excessively_nested_manifest_without_creating_destination(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)

    (backup / "manifest.json").write_text("{\"nested\":" * 10000 + "0" + "}" * 10000, encoding="utf-8")
    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match="exceeds parser nesting limits"):
        restore_backup(backup, destination)
    assert not destination.exists()


@pytest.mark.parametrize("manifest_payload", [
    '{"format_version": 1, "format_version": 1, "sqlite_integrity_check": "ok"}',
    '{"format_version": 1, "sqlite_integrity_check": "ok", "nested": {"x": 1, "x": 2}}',
])
def test_restore_rejects_duplicate_manifest_keys(tmp_path, manifest_payload):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    (backup / "manifest.json").write_text(manifest_payload, encoding="utf-8")

    destination = tmp_path / "recovered"
    with pytest.raises(ValueError, match="Duplicate key in backup manifest"):
        restore_backup(backup, destination)
    assert not destination.exists()


def test_restore_rejects_invalid_evidence_manifest_digest(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "receipt.bin").write_bytes(b"proof")
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evidence_files"][0]["sha256"] = "not-a-sha256"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    destination = tmp_path / "recovered"

    with pytest.raises(ValueError, match="checksum"):
        restore_backup(backup, destination)
    assert not destination.exists()


def test_restore_rejects_oversized_manifest_without_creating_destination(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    (backup / "manifest.json").write_bytes(b" " * (16 * 1024 * 1024 + 1))
    destination = tmp_path / "recovered"

    with pytest.raises(ValueError, match="16 MiB safety limit"):
        restore_backup(backup, destination)
    assert not destination.exists()


def test_backup_rejects_malformed_existing_evidence_schema(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE earnings_evidence (stored_name TEXT)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    with pytest.raises(RuntimeError, match="Invalid earnings_evidence schema"):
        create_backup(database, evidence, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()


def test_restore_rejects_malformed_existing_evidence_schema(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    backup_db = backup / "autoearn.db"
    with sqlite3.connect(backup_db) as db:
        db.execute("CREATE TABLE earnings_evidence (stored_name TEXT)")
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    database_bytes = backup_db.read_bytes()
    manifest["database_size_bytes"] = len(database_bytes)
    manifest["database_sha256"] = hashlib.sha256(database_bytes).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    destination = tmp_path / "recovered"
    with pytest.raises(ValueError, match="Invalid earnings_evidence schema"):
        restore_backup(backup, destination)
    assert not destination.exists()


def test_backup_and_restore_preserve_quarantine_subdirectory(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "private_evidence"
    quarantine = evidence / ".quarantine"
    quarantine.mkdir(parents=True)
    (quarantine / "orphan.orphan").write_bytes(b"recoverable orphan")
    backup = tmp_path / "backup"
    manifest = create_backup(database, evidence, backup)

    assert manifest["evidence_files"][0]["name"] == ".quarantine/orphan.orphan"
    restored = tmp_path / "restored"
    restore_backup(backup, restored)
    assert (restored / "private_evidence" / ".quarantine" / "orphan.orphan").read_bytes() == b"recoverable orphan"


@pytest.mark.parametrize("unsafe_name", [
    "../escape.bin",
    "nested\\\\escape.bin",
    "C:/escape.bin",
    "nested/../escape.bin",
    "trailing-dot.",
    "trailing-space ",
    "x" * 256,
    "a" * 1025,
])
def test_restore_rejects_nonportable_or_oversized_evidence_paths(tmp_path, unsafe_name):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "receipt.bin").write_bytes(b"receipt")
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)

    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evidence_files"][0]["name"] = unsafe_name
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    destination = tmp_path / "recovered"
    with pytest.raises(ValueError, match="Unsafe evidence filename"):
        restore_backup(backup, destination)
    assert not destination.exists()


def test_restore_preserves_owner_only_permissions_on_posix(tmp_path):
    import os
    import stat

    if os.name != "posix":
        pytest.skip("POSIX permission modes are not available")
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "private_evidence"
    nested = evidence / ".quarantine" / "nested"
    nested.mkdir(parents=True)
    (nested / "orphan.orphan").write_bytes(b"recoverable evidence")

    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    restored = tmp_path / "restored"
    restore_backup(backup, restored)

    assert stat.S_IMODE((restored / "autoearn.db").stat().st_mode) == 0o600
    assert stat.S_IMODE((restored / "manifest.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((restored / "private_evidence").stat().st_mode) == 0o700
    assert stat.S_IMODE((restored / "private_evidence" / ".quarantine").stat().st_mode) == 0o700
    assert stat.S_IMODE((restored / "private_evidence" / ".quarantine" / "nested").stat().st_mode) == 0o700
    assert stat.S_IMODE((restored / "private_evidence" / ".quarantine" / "nested" / "orphan.orphan").stat().st_mode) == 0o600


def test_restore_rejects_unlisted_extra_evidence_file(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "receipt.bin").write_bytes(b"expected receipt")
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)
    (backup / "private_evidence" / "unlisted.bin").write_bytes(b"not in manifest")

    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match="do not match the manifest"):
        restore_backup(backup, destination)
    assert not destination.exists()


def test_restore_rejects_symlink_inside_evidence_tree(tmp_path):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "receipt.bin").write_bytes(b"expected receipt")
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)

    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"must not be followed")
    try:
        (backup / "private_evidence" / "linked.bin").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform")

    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match="unsafe entry"):
        restore_backup(backup, destination)
    assert not destination.exists()


@pytest.mark.parametrize("unsafe_name", [
    "CON",
    "nul.txt",
    "AUX.data",
    "COM1.log",
    "LPT9",
    "bad<name>.bin",
    "bad|name.bin",
    "bad?name.bin",
])
def test_restore_rejects_windows_reserved_or_invalid_evidence_components(tmp_path, unsafe_name):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "receipt.bin").write_bytes(b"receipt")
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)

    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    (backup / "private_evidence" / "receipt.bin").rename(
        backup / "private_evidence" / unsafe_name
    )
    manifest["evidence_files"][0]["name"] = unsafe_name
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match="Unsafe evidence filename"):
        restore_backup(backup, destination)
    assert not destination.exists()


def test_restore_rejects_case_colliding_evidence_paths_on_posix(tmp_path):
    import os

    if os.name != "posix":
        pytest.skip("Case-colliding filenames require a case-sensitive test filesystem")
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "Receipt.bin").write_bytes(b"first")
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)

    extra = backup / "private_evidence" / "receipt.bin"
    extra.write_bytes(b"second")
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evidence_files"].append({
        "name": "receipt.bin",
        "size_bytes": extra.stat().st_size,
        "sha256": hashlib.sha256(extra.read_bytes()).hexdigest(),
    })
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match="case-colliding"):
        restore_backup(backup, destination)
    assert not destination.exists()


def test_restore_rejects_unicode_normalization_colliding_paths(tmp_path):
    import os

    if os.name != "posix":
        pytest.skip("Distinct normalization forms require a case-sensitive POSIX test filesystem")
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    composed = "caf\u00e9.txt"
    (evidence / composed).write_bytes(b"first")
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)

    decomposed = "cafe\u0301.txt"
    extra = backup / "private_evidence" / decomposed
    extra.write_bytes(b"second")
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evidence_files"].append({
        "name": decomposed,
        "size_bytes": extra.stat().st_size,
        "sha256": hashlib.sha256(extra.read_bytes()).hexdigest(),
    })
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match="case-colliding"):
        restore_backup(backup, destination)
    assert not destination.exists()


@pytest.mark.parametrize("unsafe_name", [
    "CON", "nul.txt", "AUX.data", "COM1.log", "LPT9",
    "bad<name>.bin", "bad|name.bin", "bad?name.bin",
])
def test_backup_rejects_nonportable_evidence_names(tmp_path, unsafe_name):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / unsafe_name).write_bytes(b"receipt")

    destination = tmp_path / "backup"
    with pytest.raises(ValueError, match="Unsafe evidence filename"):
        create_backup(database, evidence, destination)
    assert not destination.exists()


def test_backup_rejects_case_colliding_evidence_names_on_posix(tmp_path):
    import os

    if os.name != "posix":
        pytest.skip("Case-colliding filenames require a case-sensitive test filesystem")
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "Receipt.bin").write_bytes(b"first")
    (evidence / "receipt.bin").write_bytes(b"second")

    with pytest.raises(ValueError, match="case-colliding"):
        create_backup(database, evidence, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()


def test_backup_rejects_unicode_normalization_colliding_names_on_posix(tmp_path):
    import os

    if os.name != "posix":
        pytest.skip("Distinct normalization forms require a case-sensitive POSIX test filesystem")
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "caf\u00e9.txt").write_bytes(b"first")
    (evidence / "cafe\u0301.txt").write_bytes(b"second")

    with pytest.raises(ValueError, match="case-colliding"):
        create_backup(database, evidence, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()


@pytest.mark.parametrize("unsafe_name", [
    "..\\outside.db",
    "C:\\outside.db",
    "bad:name.db",
    "CON",
    "nul.db",
    "trailing-dot.",
    "trailing-space ",
])
def test_restore_rejects_nonportable_database_filename(tmp_path, unsafe_name):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)

    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["database_file"] = unsafe_name
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match="Invalid database filename"):
        restore_backup(backup, destination)
    assert not destination.exists()


@pytest.mark.parametrize("unsafe_name", ["CON", "nul.db", "bad:name.db", "trailing-dot."])
def test_backup_rejects_nonportable_database_filename(tmp_path, unsafe_name):
    database = tmp_path / unsafe_name
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()

    with pytest.raises(ValueError, match="Unsafe evidence filename"):
        create_backup(database, evidence, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()



@pytest.mark.parametrize("manifest_field,unsafe_name,error_match", [
    ("database_file", "\ud800", "Invalid database filename"),
    ("evidence_files", "\ud800", "valid Unicode"),
])
def test_restore_rejects_lone_surrogate_filenames_without_creating_destination(
    tmp_path, manifest_field, unsafe_name, error_match
):
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "receipt.bin").write_bytes(b"receipt")
    backup = tmp_path / "backup"
    create_backup(database, evidence, backup)

    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest_field == "database_file":
        manifest[manifest_field] = unsafe_name
    else:
        manifest[manifest_field][0]["name"] = unsafe_name
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match=error_match):
        restore_backup(backup, destination)
    assert not destination.exists()


def test_backup_rejects_undecodable_posix_evidence_filename(tmp_path):
    import os

    if os.name != "posix":
        pytest.skip("Undecodable filesystem names use POSIX surrogateescape")
    database = tmp_path / "autoearn.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value INTEGER)")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    bad_name = os.fsdecode(b"receipt_\xff.bin")
    bad_path = evidence / bad_name
    try:
        descriptor = os.open(os.fsencode(bad_path), os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(descriptor)
    except (OSError, UnicodeError):
        pytest.skip("Filesystem does not support undecodable byte filenames")

    with pytest.raises(ValueError, match="valid Unicode"):
        create_backup(database, evidence, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()


def test_json_nesting_guard_ignores_braces_and_escaped_quotes_inside_strings():
    payload = json.dumps({
        "note": 'escaped quote: " and backslash: \\ followed by braces ' + "{" * 200 + "}" * 200
    })
    _reject_excessive_json_nesting(payload)
