"""Read-only ClamAV readiness probe for local production monitoring.

Checks loopback clamd PING/PONG and local signature database age. It never
starts, stops, updates, or reconfigures the daemon.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3310
DEFAULT_TIMEOUT = 3.0
DEFAULT_MAX_SIGNATURE_AGE_HOURS = 24


def probe_clamd(*, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT) -> bool:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port must be an integer between 1 and 65535")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
        raise ValueError("timeout must be between 0 and 30 seconds")
    try:
        with socket.create_connection((DEFAULT_HOST, port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(b"zPING\0")
            response = conn.recv(32)
        return response.strip(b"\0\r\n") == b"PONG"
    except (OSError, TimeoutError):
        return False


def signature_status(database_dir: Path, *, max_age_hours: int = DEFAULT_MAX_SIGNATURE_AGE_HOURS,
                     now: datetime | None = None) -> dict:
    if isinstance(max_age_hours, bool) or not isinstance(max_age_hours, int) or max_age_hours < 1:
        raise ValueError("max_age_hours must be a positive integer")
    directory = Path(database_dir).expanduser().absolute()
    for component in (directory, *directory.parents):
        if component.is_symlink():
            raise ValueError("signature database path must not contain symbolic links")
    if not directory.is_dir():
        return {"healthy": False, "reason": "signature_directory_missing", "file_count": 0}
    files = sorted(path for path in directory.iterdir()
                   if path.suffix.lower() in {".cvd", ".cld"} and path.is_file() and not path.is_symlink())
    if not files:
        return {"healthy": False, "reason": "signature_files_missing", "file_count": 0}
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    age_hours = max(0.0, current.timestamp() - max(path.stat().st_mtime for path in files)) / 3600
    healthy = age_hours <= max_age_hours
    return {"healthy": healthy, "reason": "fresh" if healthy else "signatures_stale",
            "file_count": len(files), "newest_signature_age_hours": round(age_hours, 2),
            "max_age_hours": max_age_hours}


def build_report(database_dir: Path, *, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT,
                 max_age_hours: int = DEFAULT_MAX_SIGNATURE_AGE_HOURS,
                 now: datetime | None = None) -> dict:
    daemon_ok = probe_clamd(port=port, timeout=timeout)
    signatures = signature_status(database_dir, max_age_hours=max_age_hours, now=now)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return {"healthy": daemon_ok and signatures["healthy"],
            "checked_at": checked_at.astimezone(timezone.utc).isoformat(),
            "daemon": {"healthy": daemon_ok, "host": DEFAULT_HOST, "port": port},
            "signatures": signatures, "actions_taken": []}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only local ClamAV health/signature freshness probe.")
    parser.add_argument("--database-dir", default="/var/lib/clamav")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--max-age-hours", type=int, default=DEFAULT_MAX_SIGNATURE_AGE_HOURS)
    args = parser.parse_args()
    try:
        report = build_report(Path(args.database_dir), port=args.port, timeout=args.timeout,
                              max_age_hours=args.max_age_hours)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
