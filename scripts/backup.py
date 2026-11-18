"""Create a consistent, integrity-checked local backup of AutoEarn AI data.

Usage:
    python scripts/backup.py [destination-directory]

The backup contains a SQLite online-backup snapshot, private evidence files,
and a SHA-256 manifest. Keep the destination on encrypted storage.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unicodedata

ROOT = Path(__file__).resolve().parents[1]


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



def _portable_evidence_key(name: str) -> str:
    """Validate a portable evidence path and return its collision key."""
    relative_name = Path(name)
    if (
        not name or relative_name.is_absolute()
        or relative_name.as_posix() != name
        or "\\\\" in name or any(char in name for char in '<>:"|?*')
        or len(name.encode("utf-8")) > 1024
        or any(
            not part or part in {".", ".."} or part.endswith((" ", "."))
            or len(part.encode("utf-8")) > 255
            or part.split(".", 1)[0].upper() in {"CON", "PRN", "AUX", "NUL"}
            or (
                len(part.split(".", 1)[0]) == 4
                and part.split(".", 1)[0].upper()[:3] in {"COM", "LPT"}
                and part.split(".", 1)[0].upper()[3] in "123456789"
            )
            for part in relative_name.parts
        )
        or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in name)
    ):
        raise ValueError(f"Unsafe evidence filename: {name}")
    return unicodedata.normalize("NFC", name).casefold()


def _read_evidence_rows(db: sqlite3.Connection) -> list[tuple]:
    """Read evidence references, allowing legacy databases with no table."""
    table = db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'earnings_evidence'").fetchone()
    if table is None:
        return []
    columns = {row[1] for row in db.execute("PRAGMA table_info(earnings_evidence)")}
    required = {"stored_name", "size_bytes", "sha256"}
    if not required.issubset(columns):
        missing = ", ".join(sorted(required - columns))
        raise RuntimeError(f"Invalid earnings_evidence schema; missing columns: {missing}")
    return db.execute("SELECT stored_name, size_bytes, sha256 FROM earnings_evidence").fetchall()


def create_backup(
    database_path: Path,
    evidence_dir: Path,
    destination: Path,
) -> dict:
    """Build a complete backup at destination without overwriting prior backups."""
    # Check lexical paths first: resolve() would follow a symlink and hide it.
    _reject_symlink_components(database_path)
    _reject_symlink_components(evidence_dir)
    _reject_symlink_components(destination)
    database_path = Path(database_path).resolve()
    evidence_dir = Path(evidence_dir).resolve()
    destination = Path(destination).resolve()

    if not database_path.is_file():
        raise FileNotFoundError(f"Database file does not exist: {database_path}")
    if destination.exists():
        raise FileExistsError(f"Backup destination already exists: {destination}")
    if destination == database_path or destination == evidence_dir:
        raise ValueError("Backup destination must be separate from source data")
    if evidence_dir.exists() and (
        destination == evidence_dir or evidence_dir in destination.parents
    ):
        raise ValueError("Backup destination cannot be inside the evidence directory")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".autoearn-backup-", dir=destination.parent))
    try:
        database_copy = staging / database_path.name
        with closing(sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(database_copy)) as target:
                source.backup(target)
                integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise RuntimeError(f"SQLite backup integrity check failed: {integrity}")
        if os.name == "posix":
            os.chmod(database_copy, 0o600)

        with closing(sqlite3.connect(database_copy)) as snapshot:
            evidence_rows = _read_evidence_rows(snapshot)

        evidence_copy = staging / "private_evidence"
        evidence_copy.mkdir(mode=0o700)
        evidence_entries = []
        portable_names = set()
        if evidence_dir.exists():
            if not evidence_dir.is_dir():
                raise ValueError("Evidence path is not a directory")
            for item in sorted(evidence_dir.rglob("*"), key=lambda path: path.as_posix()):
                if item.is_symlink():
                    raise ValueError(f"Evidence symlinks are not backed up: {item.relative_to(evidence_dir)}")
                if item.is_dir():
                    continue
                if not item.is_file():
                    raise ValueError(f"Unexpected non-file in evidence directory: {item.relative_to(evidence_dir)}")
                relative_name = item.relative_to(evidence_dir).as_posix()
                portable_key = _portable_evidence_key(relative_name)
                if portable_key in portable_names:
                    raise ValueError(
                        f"Duplicate or case-colliding evidence filename: {relative_name}"
                    )
                portable_names.add(portable_key)
                copied = evidence_copy / relative_name
                copied.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copyfile(item, copied)
                if os.name == "posix":
                    os.chmod(copied, 0o600)
                evidence_entries.append({
                    "name": relative_name,
                    "size_bytes": copied.stat().st_size,
                    "sha256": _sha256(copied),
                })

        copied_by_name = {entry["name"]: entry for entry in evidence_entries}
        for stored_name, size_bytes, sha256 in evidence_rows:
            copied = copied_by_name.get(stored_name)
            if copied is None or copied["size_bytes"] != size_bytes or copied["sha256"] != sha256:
                raise RuntimeError(
                    "Evidence files do not match the SQLite snapshot; stop the app and retry the backup"
                )

        manifest = {
            "format_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_file": database_copy.name,
            "database_size_bytes": database_copy.stat().st_size,
            "database_sha256": _sha256(database_copy),
            "sqlite_integrity_check": integrity,
            "evidence_directory": "private_evidence",
            "evidence_files": evidence_entries,
            "database_evidence_records_checked": len(evidence_rows),
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if os.name == "posix":
            os.chmod(manifest_path, 0o600)
            os.chmod(evidence_copy, 0o700)
            os.chmod(staging, 0o700)
        os.replace(staging, destination)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up AutoEarn AI's local database and private evidence.")
    parser.add_argument("destination", nargs="?", help="New backup directory (must not already exist)")
    args = parser.parse_args()

    database = Path(os.getenv("AUTOEARN_DB", ROOT / "autoearn.db"))
    evidence = Path(os.getenv("AUTOEARN_EVIDENCE_DIR", ROOT / "private_evidence"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = Path(args.destination) if args.destination else ROOT / "backups" / f"autoearn-{stamp}"
    manifest = create_backup(database, evidence, destination)
    print(f"Backup created: {destination.resolve()}")
    print(f"Database SHA-256: {manifest['database_sha256']}")
    print(f"Evidence files: {len(manifest['evidence_files'])}")
    print("SQLite integrity: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
