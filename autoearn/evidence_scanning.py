"""Fail-closed client for a local ClamAV daemon using the INSTREAM protocol.

The evidence upload route invokes this client before persisting an upload. A
definitive clean verdict is required; scanner errors and positive detections
prevent storage. Production still requires a separately managed ClamAV daemon
with current signatures bound only to loopback.
"""
from __future__ import annotations
import socket

CHUNK_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 4096
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_PORT = 3310

class ScannerUnavailable(RuntimeError):
    """The scanner could not provide a definitive verdict."""

class MalwareDetected(RuntimeError):
    """The scanner returned a definitive positive malware verdict."""

def scan_bytes(payload: bytes, *, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Send bytes to loopback ClamAV; accept only an exact clean verdict."""
    if not isinstance(payload, bytes) or not payload:
        raise ValueError("A non-empty bytes payload is required.")
    if not 1 <= port <= 65535 or not 0 < timeout <= 30:
        raise ValueError("Invalid local scanner connection settings.")
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(b"zINSTREAM\0")
            for offset in range(0, len(payload), CHUNK_BYTES):
                chunk = payload[offset:offset + CHUNK_BYTES]
                conn.sendall(len(chunk).to_bytes(4, "big"))
                conn.sendall(chunk)
            conn.sendall((0).to_bytes(4, "big"))
            response = bytearray()
            while len(response) <= MAX_RESPONSE_BYTES:
                part = conn.recv(min(1024, MAX_RESPONSE_BYTES + 1 - len(response)))
                if not part:
                    break
                response.extend(part)
                if b"\0" in part or b"\n" in part:
                    break
    except (OSError, TimeoutError) as exc:
        raise ScannerUnavailable("Local malware scanner did not provide a verdict.") from exc
    if len(response) > MAX_RESPONSE_BYTES:
        raise ScannerUnavailable("Local malware scanner response exceeded its limit.")
    verdict = bytes(response).strip(b"\0\r\n")
    if verdict == b"stream: OK":
        return verdict.decode("ascii")
    if verdict.startswith(b"stream: ") and verdict.endswith(b" FOUND"):
        raise MalwareDetected("Malware scanner detected a threat.")
    raise ScannerUnavailable("Local malware scanner returned an unknown verdict.")
