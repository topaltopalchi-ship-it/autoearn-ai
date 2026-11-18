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
import unicodedata


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


def _utf8_byte_length(value: str) -> int:
    """Return strict UTF-8 length, rejecting lone surrogate code points."""
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("Filename is not valid Unicode in backup manifest") from exc


def _is_windows_reserved_component(component: str) -> bool:
    """Return whether a path component is reserved by Windows, even with an extension."""
    stem = component.split(".", 1)[0].upper()
    if stem in {"CON", "PRN", "AUX", "NUL"}:
        return True
    if len(stem) == 4 and stem[:3] in {"COM", "LPT"} and stem[3] in "123456789":
        return True
    return False


def restore_backup(backup_directory: Path, destination: Path) -> dict:
    """Verify all backup data and restore it into a new, non-existing directory."""
    # Validate the original path components before resolve() follows links.
    _reject_symlink_components(backup_directory)
    _reject_symlink_components(destination)
    backup_directory = Path(backup_directory).resolve()
    destination = Path(destination).resolve()
    if not backup_directory.is_dir():
        raise FileNotFoundError("Backup directory does not exist")
    if destination == backup_directory or backup_directory in destination.parents:
        raise ValueError("Restore destination must be outside the backup directory")
    if destination.exists():
        raise FileExistsError(f"Restore destination already exists: {destination}")
    manifest_path = backup_directory / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("Backup manifest is missing or unsafe")
    if manifest_path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Backup manifest exceeds the 16 MiB safety limit")
    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate key in backup manifest: {key}")
            result[key] = value
        return result

    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
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
    try:
        database_name_byte_length = (
            _utf8_byte_length(database_name) if isinstance(database_name, str) else 0
        )
    except ValueError as exc:
        raise ValueError("Invalid database filename in backup manifest") from exc
    if (
        not isinstance(database_name, str) or not database_name
        or Path(database_name).name != database_name
        or Path(database_name).is_absolute()
        or "\\" in database_name
        or any(char in database_name for char in '<>:"|?*')
        or database_name.endswith((" ", "."))
        or database_name_byte_length > 255
        or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in database_name)
        or _is_windows_reserved_component(database_name)
        or database_name.casefold() in {"manifest.json", "private_evidence"}
    ):
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
    portable_names = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Invalid evidence entry")
        name = entry.get("name")
        # Backup paths use portable POSIX separators regardless of the host
        # running restore. Reject Windows separators/drive or alternate-stream
        # syntax too, rather than allowing a manifest to change meaning when
        # moved between operating systems.
        relative_name = Path(name) if isinstance(name, str) else None
        if (
            relative_name is None or not name or relative_name.is_absolute()
            or relative_name.as_posix() != name
            or "\\" in name or any(char in name for char in '<>:"|?*')
            or _utf8_byte_length(name) > 1024
            or any(
                not part or part in {".", ".."} or part.endswith((" ", "."))
                or _is_windows_reserved_component(part)
                or _utf8_byte_length(part) > 255
                for part in relative_name.parts
            )
            or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in name)
        ):
            raise ValueError("Unsafe evidence filename in backup manifest")
        portable_key = unicodedata.normalize("NFC", name).casefold()
        if portable_key in portable_names:
            raise ValueError("Duplicate or case-colliding evidence filename in backup manifest")
        portable_names.add(portable_key)
        entry_size = entry.get("size_bytes")
        if isinstance(entry_size, bool) or not isinstance(entry_size, int) or entry_size < 0:
            raise ValueError("Invalid evidence size in backup manifest")
        if not valid_digest(entry.get("sha256")):
            raise ValueError("Invalid evidence checksum in backup manifest")
        expected[name] = entry
    actual_names = set()
    for item in source_evidence.rglob("*"):
        if item.is_symlink():
            raise ValueError("Backup evidence contains an unsafe entry")
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValueError("Backup evidence contains an unsafe entry")
        actual_names.add(item.relative_to(source_evidence).as_posix())
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
            copied.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
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
            for item in evidence_copy.rglob("*"):
                if item.is_dir():
                    os.chmod(item, 0o700)
                elif item.is_file():
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
