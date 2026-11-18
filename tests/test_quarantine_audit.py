from datetime import datetime, timedelta, timezone
import hashlib
import os

import pytest

from scripts.audit_quarantine import audit_quarantine


def test_quarantine_audit_hashes_files_and_only_flags_old_items(tmp_path):
    quarantine = tmp_path / ".quarantine"
    quarantine.mkdir()
    old = quarantine / "old.bin"
    recent = quarantine / "nested" / "recent.bin"
    recent.parent.mkdir()
    old.write_bytes(b"old evidence")
    recent.write_bytes(b"recent evidence")
    now = datetime(2026, 11, 18, tzinfo=timezone.utc)
    old_time = (now - timedelta(days=400)).timestamp()
    recent_time = (now - timedelta(days=10)).timestamp()
    os.utime(old, (old_time, old_time))
    os.utime(recent, (recent_time, recent_time))

    report = audit_quarantine(quarantine, now=now)

    assert report["file_count"] == 2
    assert report["policy"] == {
        "review_after_days": 365,
        "action": "manual_review_only",
        "automatic_deletion": False,
        "automatic_restore": False,
        "automatic_reclassification": False,
    }
    by_name = {entry["name"]: entry for entry in report["files"]}
    assert by_name["old.bin"]["retention_status"] == "review_required"
    assert by_name["old.bin"]["sha256"] == hashlib.sha256(b"old evidence").hexdigest()
    assert by_name["nested/recent.bin"]["retention_status"] == "retain"
    assert old.read_bytes() == b"old evidence"
    assert recent.read_bytes() == b"recent evidence"


def test_quarantine_audit_rejects_symlinks_without_following_them(tmp_path):
    quarantine = tmp_path / ".quarantine"
    quarantine.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"do not inspect")
    link = quarantine / "linked"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable")
    with pytest.raises(ValueError, match="symbolic link"):
        audit_quarantine(quarantine)
    assert outside.read_bytes() == b"do not inspect"


@pytest.mark.parametrize("days", [0, -1, True, 1.5])
def test_quarantine_audit_rejects_invalid_review_period(tmp_path, days):
    quarantine = tmp_path / ".quarantine"
    quarantine.mkdir()
    with pytest.raises(ValueError, match="positive integer"):
        audit_quarantine(quarantine, review_after_days=days)


def test_quarantine_audit_rejects_naive_clock_and_missing_directory(tmp_path):
    with pytest.raises(ValueError, match="timezone-aware"):
        audit_quarantine(tmp_path, now=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="existing"):
        audit_quarantine(tmp_path / "missing")
