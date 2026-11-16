import httpx

from app import provider_checks


def test_openai_check_reports_connected_without_returning_response_body(monkeypatch):
    seen = {}

    def fake_get(url, *, headers, timeout, follow_redirects):
        seen.update(url=url, headers=headers, timeout=timeout, follow_redirects=follow_redirects)
        return httpx.Response(200, json={"data": [{"id": "model"}]})

    monkeypatch.setattr(provider_checks.httpx, "get", fake_get)
    result = provider_checks.check_openai_api_key("sk-test-secret")
    assert result == {"status": "connected", "connected": True}
    assert seen["url"] == "https://api.openai.com/v1/models"
    assert seen["headers"]["Authorization"] == "Bearer sk-test-secret"
    assert seen["timeout"] == 8.0
    assert seen["follow_redirects"] is False
    assert "sk-test-secret" not in str(result)


def test_openai_check_distinguishes_invalid_key(monkeypatch):
    monkeypatch.setattr(
        provider_checks.httpx, "get",
        lambda *args, **kwargs: httpx.Response(401, text="do not expose provider response"),
    )
    assert provider_checks.check_openai_api_key("sk-invalid") == {
        "status": "invalid_credential", "connected": False
    }


def test_openai_check_does_not_follow_redirects(monkeypatch):
    monkeypatch.setattr(
        provider_checks.httpx, "get",
        lambda *args, **kwargs: httpx.Response(302, headers={"Location": "https://attacker.invalid"}),
    )
    assert provider_checks.check_openai_api_key("sk-test") == {
        "status": "unexpected_redirect", "connected": False
    }


def test_openai_check_handles_timeout_without_leaking_details(monkeypatch):
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("secret-bearing transport detail")
    monkeypatch.setattr(provider_checks.httpx, "get", timeout)
    result = provider_checks.check_openai_api_key("sk-test")
    assert result == {"status": "timeout", "connected": False}
    assert "secret-bearing" not in str(result)
