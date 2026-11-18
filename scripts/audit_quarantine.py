"""Create a non-destructive audit inventory of orphan-evidence quarantine.

This tool never deletes, moves, restores, or reclassifies files. Files older than
the review threshold are flagged for an owner-reviewed retention decision only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_quarantine(
    quarantine_dir: Path,
    review_after_days: int = 365,
    now: datetime | None = None,
) -> dict:
    """Return a deterministic inventory; never mutate the quarantine directory."""
    if isinstance(review_after_days, bool) or not isinstance(review_after_days, int) or review_after_days < 1:
        raise ValueError("review_after_days must be a positive integer")
    quarantine_dir = Path(os.path.abspath(Path(quarantine_dir).expanduser()))
    for component in (quarantine_dir, *quarantine_dir.parents):
        if component.is_symlink():
            raise ValueError("Quarantine path must not contain symbolic links")
    if not quarantine_dir.is_dir():
        raise ValueError("Quarantine path must be an existing directory")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    cutoff = current - timedelta(days=review_after_days)
    entries = []
    for item in sorted(quarantine_dir.rglob("*"), key=lambda path: path.as_posix()):
        if item.is_symlink():
            raise ValueError(f"Quarantine contains a symbolic link: {item.relative_to(quarantine_dir)}")
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValueError(f"Quarantine contains a non-regular entry: {item.relative_to(quarantine_dir)}")
        stat_result = item.stat()
        modified = datetime.fromtimestamp(stat_result.st_mtime, timezone.utc)
        entries.append({
            "name": item.relative_to(quarantine_dir).as_posix(),
            "size_bytes": stat_result.st_size,
            "sha256": _sha256(item),
            "modified_at": modified.isoformat(),
            "retention_status": "review_required" if modified <= cutoff else "retain",
        })
    return {
        "format_version": 1,
        "created_at": current.isoformat(),
        "policy": {
            "review_after_days": review_after_days,
            "action": "manual_review_only",
            "automatic_deletion": False,
            "automatic_restore": False,
            "automatic_reclassification": False,
        },
        "file_count": len(entries),
        "files": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory orphan-evidence quarantine without changing any files."
    )
    parser.add_argument(
        "quarantine_directory",
        nargs="?",
        default=os.getenv("AUTOEARN_EVIDENCE_DIR", "private_evidence") + "/.quarantine",
    )
    parser.add_argument("--review-after-days", type=int, default=365)
    parser.add_argument("--output", help="Optional report path outside the quarantine directory")
    args = parser.parse_args()
    report = audit_quarantine(Path(args.quarantine_directory), args.review_after_days)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(os.path.abspath(Path(args.output).expanduser()))
        quarantine_root = Path(os.path.abspath(Path(args.quarantine_directory).expanduser()))
        if output == quarantine_root or quarantine_root in output.parents:
            parser.error("output path must be outside the quarantine directory")
        for component in (output, *output.parents):
            if component.is_symlink():
                parser.error("output path must not contain symbolic links")
        if output.exists():
            parser.error("output path must be new")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        if os.name == "posix":
            os.chmod(output, 0o600)
        print(f"Quarantine audit written: {output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
