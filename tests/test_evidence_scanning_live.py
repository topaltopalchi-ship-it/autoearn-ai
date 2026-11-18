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
