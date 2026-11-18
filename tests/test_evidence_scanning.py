import pytest
from autoearn.evidence_scanning import MalwareDetected, ScannerUnavailable, scan_bytes

class FakeSocket:
    def __init__(self, response=b"stream: OK\0"):
        self.response = response
        self.sent = bytearray()
        self.timeout = None
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def settimeout(self, value): self.timeout = value
    def sendall(self, value): self.sent.extend(value)
    def recv(self, size):
        result, self.response = self.response[:size], self.response[size:]
        return result

def test_clamav_stream_protocol_accepts_exact_clean_verdict(monkeypatch):
    fake = FakeSocket()
    monkeypatch.setattr("autoearn.evidence_scanning.socket.create_connection", lambda address, timeout: fake)
    assert scan_bytes(b"PDF test") == "stream: OK"
    assert fake.timeout == 5.0
    assert fake.sent.startswith(b"zINSTREAM\0")
    assert fake.sent.endswith((0).to_bytes(4, "big"))

def test_clamav_stream_protocol_sends_length_prefixed_chunks(monkeypatch):
    from autoearn import evidence_scanning
    payload = b"x" * (evidence_scanning.CHUNK_BYTES + 3)
    fake = FakeSocket()
    monkeypatch.setattr("autoearn.evidence_scanning.socket.create_connection", lambda address, timeout: fake)
    assert scan_bytes(payload) == "stream: OK"
    wire = bytes(fake.sent)[len(b"zINSTREAM\0"): ]
    first_length = int.from_bytes(wire[:4], "big")
    assert first_length == evidence_scanning.CHUNK_BYTES
    second_offset = 4 + first_length
    assert int.from_bytes(wire[second_offset:second_offset + 4], "big") == 3

def test_clamav_positive_verdict_is_rejected(monkeypatch):
    fake = FakeSocket(b"stream: /tmp/file: Eicar-Test-Signature FOUND\0")
    monkeypatch.setattr("autoearn.evidence_scanning.socket.create_connection", lambda address, timeout: fake)
    with pytest.raises(MalwareDetected): scan_bytes(b"malware fixture")

@pytest.mark.parametrize("response", [b"", b"ERROR\0", b"stream: OK extra\0"])
def test_clamav_unknown_or_empty_verdict_fails_closed(monkeypatch, response):
    fake = FakeSocket(response)
    monkeypatch.setattr("autoearn.evidence_scanning.socket.create_connection", lambda address, timeout: fake)
    with pytest.raises(ScannerUnavailable): scan_bytes(b"test")

def test_clamav_connection_failure_fails_closed(monkeypatch):
    def unavailable(*_args, **_kwargs): raise OSError("daemon unavailable")
    monkeypatch.setattr("autoearn.evidence_scanning.socket.create_connection", unavailable)
    with pytest.raises(ScannerUnavailable): scan_bytes(b"test")

@pytest.mark.parametrize("payload", [b"", "not bytes", None])
def test_clamav_requires_non_empty_bytes(payload):
    with pytest.raises(ValueError): scan_bytes(payload)
