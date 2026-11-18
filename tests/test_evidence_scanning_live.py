"""Opt-in live tests for a locally provisioned ClamAV daemon.

Run only in an isolated test environment with clamd listening on loopback
127.0.0.1:3310 and current signatures:
    AUTOEARN_CLAMAV_INTEGRATION=1 python -m pytest -q tests/test_evidence_scanning_live.py
"""
import os

import pytest

from autoearn.evidence_scanning import MalwareDetected, scan_bytes

pytestmark = pytest.mark.skipif(
    os.environ.get("AUTOEARN_CLAMAV_INTEGRATION") != "1",
    reason="set AUTOEARN_CLAMAV_INTEGRATION=1 to run against a real local ClamAV daemon",
)


def test_live_clamav_accepts_harmless_fixture():
    assert scan_bytes(b"AutoEarn harmless scanner integration fixture\n") == "stream: OK"


def test_live_clamav_rejects_standard_eicar_test_signature():
    # EICAR is a harmless industry-standard antivirus test string, not malware.
    eicar = (
        b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$"
        b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    )
    with pytest.raises(MalwareDetected):
        scan_bytes(eicar)


def test_live_clamav_outage_rejects_evidence_upload_without_storage(tmp_path, monkeypatch):
    """Exercise the real scanner client and upload route while clamd is unavailable."""
    import socket

    from fastapi.testclient import TestClient
    from app import main

    # Keep a loopback port bound but not listening, so the connection is
    # deterministically refused while the live ClamAV daemon remains running.
    unavailable = socket.socket()
    unavailable.bind(("127.0.0.1", 0))
    port = unavailable.getsockname()[1]

    database = tmp_path / "outage-test.sqlite3"
    evidence_dir = tmp_path / "private-evidence"
    owner_token = "live-test-owner-token-0123456789"
    monkeypatch.setattr(main, "DB_PATH", database)
    monkeypatch.setattr(main, "OWNER_TOKEN", owner_token)
    monkeypatch.setattr(main, "EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(
        main, "scan_bytes",
        lambda payload: scan_bytes(payload, port=port, timeout=0.25),
    )
    main.init_db()

    headers = {"X-AutoEarn-Owner-Token": owner_token}
    try:
        with TestClient(main.app) as client:
            earning_response = client.post(
                "/api/earnings", headers=headers,
                json={"amount": 2, "currency": "EUR"},
            )
            assert earning_response.status_code == 201
            earning_id = earning_response.json()["id"]

            upload = client.post(
                f"/api/earnings/{earning_id}/evidence",
                headers=headers,
                files={"upload": (
                    "receipt.pdf", b"%PDF-1.4\\nreceipt\\n", "application/pdf"
                )},
            )
            assert upload.status_code == 503
            # App startup may create the private directory for reconciliation;
            # an unavailable scanner must leave it without any evidence files.
            assert not evidence_dir.exists() or not any(evidence_dir.iterdir())

            listed = client.get(
                f"/api/earnings/{earning_id}/evidence", headers=headers
            )
            assert listed.status_code == 200
            assert listed.json() == []
    finally:
        unavailable.close()
