"""Safely verify and unpack an AutoEarn AI backup into a new directory.

This never overwrites the live database or evidence directory.
Usage: python scripts/restore.py BACKUP_DIRECTORY NEW_RESTORE_DIRECTORY
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile


def _reject_symlink_components(path: Path) -> None:
    """Reject symlinks in an input path before resolving it."""
    absolute = Path(os.path.abspath(Path(path).expanduser()))
    for component in (absolute, *absolute.parents):
        if component.is_symlink():
            raise ValueError(f"Symbolic links are not allowed in data paths: {component}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_evidence_rows(db: sqlite3.Connection) -> list[tuple]:
    """Read evidence references, allowing legacy databases with no table."""
    table = db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'earnings_evidence'").fetchone()
    if table is None:
        return []
    columns = {row[1] for row in db.execute("PRAGMA table_info(earnings_evidence)")}
    required = {"stored_name", "size_bytes", "sha256"}
    if not required.issubset(columns):
        missing = ", ".join(sorted(required - columns))
        raise ValueError(f"Invalid earnings_evidence schema; missing columns: {missing}")
    return db.execute("SELECT stored_name, size_bytes, sha256 FROM earnings_evidence").fetchall()


def restore_backup(backup_directory: Path, destination: Path) -> dict:
    """Verify all backup data and restore it into a new, non-existing directory."""
    # Validate the original path components before resolve() follows links.
    _reject_symlink_components(backup_directory)
    _reject_symlink_components(destination)
    backup_directory = Path(backup_directory).resolve()
    destination = Path(destination).resolve()
    if not backup_directory.is_dir():
        raise FileNotFoundError("Backup directory does not exist")
    if destination.exists():
        raise FileExistsError(f"Restore destination already exists: {destination}")
    manifest_path = backup_directory / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("Backup manifest is missing or unsafe")
    if manifest_path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Backup manifest exceeds the 16 MiB safety limit")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Backup manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Backup manifest must be a JSON object")
    version = manifest.get("format_version")
    if isinstance(version, bool) or version != 1 or manifest.get("sqlite_integrity_check") != "ok":
        raise ValueError("Unsupported or invalid backup manifest")

    def valid_digest(value: object) -> bool:
        return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)

    database_size = manifest.get("database_size_bytes")
    if isinstance(database_size, bool) or not isinstance(database_size, int) or database_size < 0:
        raise ValueError("Invalid database size in backup manifest")
    if not valid_digest(manifest.get("database_sha256")):
        raise ValueError("Invalid database checksum in backup manifest")

    database_name = manifest.get("database_file")
    if not isinstance(database_name, str) or not database_name or Path(database_name).name != database_name:
        raise ValueError("Invalid database filename in backup manifest")
    source_database = backup_directory / database_name
    if source_database.is_symlink() or not source_database.is_file():
        raise ValueError("Backup database is missing or unsafe")
    if source_database.stat().st_size != database_size:
        raise ValueError("Backup database size does not match manifest")
    if _sha256(source_database) != manifest.get("database_sha256"):
        raise ValueError("Backup database checksum does not match manifest")
    with closing(sqlite3.connect(source_database.as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup database failed SQLite integrity check")

    evidence_name = manifest.get("evidence_directory")
    if evidence_name != "private_evidence":
        raise ValueError("Invalid evidence directory in backup manifest")
    source_evidence = backup_directory / evidence_name
    if source_evidence.is_symlink() or not source_evidence.is_dir():
        raise ValueError("Backup evidence directory is missing or unsafe")
    entries = manifest.get("evidence_files")
    if not isinstance(entries, list):
        raise ValueError("Invalid evidence file list in backup manifest")
    expected = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Invalid evidence entry")
        name = entry.get("name")
        if not isinstance(name, str) or not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError("Unsafe evidence filename in backup manifest")
        if name in expected:
            raise ValueError("Duplicate evidence filename in backup manifest")
        entry_size = entry.get("size_bytes")
        if isinstance(entry_size, bool) or not isinstance(entry_size, int) or entry_size < 0:
            raise ValueError("Invalid evidence size in backup manifest")
        if not valid_digest(entry.get("sha256")):
            raise ValueError("Invalid evidence checksum in backup manifest")
        expected[name] = entry
    actual_names = set()
    for item in source_evidence.iterdir():
        if item.is_symlink() or not item.is_file():
            raise ValueError("Backup evidence contains an unsafe entry")
        actual_names.add(item.name)
    if actual_names != set(expected):
        raise ValueError("Backup evidence files do not match the manifest")
    for name, entry in expected.items():
        item = source_evidence / name
        if item.stat().st_size != entry.get("size_bytes") or _sha256(item) != entry.get("sha256"):
            raise ValueError(f"Evidence checksum or size mismatch: {name}")
    with closing(sqlite3.connect(source_database.as_uri() + "?mode=ro", uri=True)) as db:
        database_evidence = _read_evidence_rows(db)
    for name, size_bytes, sha256 in database_evidence:
        entry = expected.get(name)
        if entry is None or entry.get("size_bytes") != size_bytes or entry.get("sha256") != sha256:
            raise ValueError("Backup evidence does not match the SQLite snapshot")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".autoearn-restore-", dir=destination.parent))
    try:
        database_copy = staging / database_name
        shutil.copyfile(source_database, database_copy)
        evidence_copy = staging / evidence_name
        evidence_copy.mkdir(mode=0o700)
        for name in sorted(expected):
            copied = evidence_copy / name
            shutil.copyfile(source_evidence / name, copied)
            entry = expected[name]
            if copied.stat().st_size != entry["size_bytes"] or _sha256(copied) != entry["sha256"]:
                raise ValueError(f"Evidence changed while restoring: {name}")
        if _sha256(database_copy) != manifest["database_sha256"]:
            raise ValueError("Database changed while restoring")
        with closing(sqlite3.connect(database_copy.as_uri() + "?mode=ro", uri=True)) as restored_db:
            if restored_db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Restored database failed SQLite integrity check")
        if os.name == "posix":
            os.chmod(database_copy, 0o600)
            os.chmod(evidence_copy, 0o700)
            for item in evidence_copy.iterdir():
                os.chmod(item, 0o600)
            os.chmod(staging, 0o700)
        shutil.copyfile(manifest_path, staging / "manifest.json")
        if os.name == "posix":
            os.chmod(staging / "manifest.json", 0o600)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and restore an AutoEarn AI backup to a new directory.")
    parser.add_argument("backup_directory")
    parser.add_argument("destination", help="New directory; existing paths are never overwritten")
    args = parser.parse_args()
    manifest = restore_backup(Path(args.backup_directory), Path(args.destination))
    print(f"Verified restore created: {Path(args.destination).resolve()}")
    print(f"Evidence files restored: {len(manifest['evidence_files'])}")
    print("SQLite integrity: ok; checksums: ok")
    print("Copy the restored database/evidence into the configured paths only after stopping the app and preserving the current data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
