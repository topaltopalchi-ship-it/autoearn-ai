from datetime import datetime, timezone
import os
import pytest
from scripts.clamav_healthcheck import build_report, probe_clamd, signature_status


class FakeSocket:
    def __init__(self, response=b"PONG\0"):
        self.response, self.sent = response, b""
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def settimeout(self, _timeout): pass
    def sendall(self, data): self.sent += data
    def recv(self, _size): return self.response


def test_probe_uses_loopback_ping_and_requires_exact_pong(monkeypatch):
    fake, calls = FakeSocket(), []
    def connect(address, timeout):
        calls.append((address, timeout))
        return fake
    monkeypatch.setattr("scripts.clamav_healthcheck.socket.create_connection", connect)
    assert probe_clamd()
    assert calls == [(("127.0.0.1", 3310), 3.0)]
    assert fake.sent == b"zPING\0"


@pytest.mark.parametrize("response", [b"", b"NOPE\0", b"PONG extra\0"])
def test_probe_rejects_non_pong(monkeypatch, response):
    monkeypatch.setattr("scripts.clamav_healthcheck.socket.create_connection",
                        lambda *_a, **_k: FakeSocket(response))
    assert not probe_clamd()


def test_probe_connection_error_is_unhealthy(monkeypatch):
    def fail(*_a, **_k): raise OSError("offline")
    monkeypatch.setattr("scripts.clamav_healthcheck.socket.create_connection", fail)
    assert not probe_clamd()


def test_signature_status_reports_fresh_and_stale_files(tmp_path):
    now = datetime(2026, 11, 18, tzinfo=timezone.utc)
    signature = tmp_path / "daily.cvd"
    signature.write_bytes(b"db")
    os.utime(signature, (now.timestamp() - 3600, now.timestamp() - 3600))
    assert signature_status(tmp_path, now=now)["healthy"]
    os.utime(signature, (now.timestamp() - 30 * 3600, now.timestamp() - 30 * 3600))
    result = signature_status(tmp_path, now=now)
    assert not result["healthy"] and result["reason"] == "signatures_stale"


def test_signature_status_ignores_unrelated_files(tmp_path):
    (tmp_path / "notes.txt").write_text("not a database")
    result = signature_status(tmp_path)
    assert not result["healthy"] and result["reason"] == "signature_files_missing"


def test_signature_status_missing_directory_is_unhealthy(tmp_path):
    result = signature_status(tmp_path / "missing")
    assert not result["healthy"] and result["reason"] == "signature_directory_missing"


@pytest.mark.parametrize("age", [0, -1, True, 1.5])
def test_signature_status_rejects_invalid_age(tmp_path, age):
    with pytest.raises(ValueError):
        signature_status(tmp_path, max_age_hours=age)


def test_probe_rejects_invalid_port():
    with pytest.raises(ValueError):
        probe_clamd(port=True)


def test_report_is_read_only_and_combines_both_checks(tmp_path, monkeypatch):
    (tmp_path / "main.cvd").write_bytes(b"db")
    monkeypatch.setattr("scripts.clamav_healthcheck.probe_clamd", lambda **_kwargs: True)
    report = build_report(tmp_path)
    assert report["healthy"] and report["actions_taken"] == []
