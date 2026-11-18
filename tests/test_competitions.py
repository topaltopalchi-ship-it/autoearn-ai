import pytest

from autoearn.competitions import (
    Competition, CompetitionAdapterManifest, CompetitionAdapterRegistry,
    SubmissionReceipt, assess_competition, build_strategy,
)


def competition(**changes):
    values = dict(
        competition_id=1, title="Open logic contest",
        url="https://contest.example.com/event",
        rules_url="https://contest.example.com/rules",
        task_type="logic", country="Germany", eligibility="eligible",
        terms_verified=True, automated_agents_allowed=True, official_api=True,
        allowed_actions=("submit_entry",),
    )
    values.update(changes)
    return Competition(**values)


@pytest.mark.parametrize("changes", [
    {"competition_id": True},
    {"competition_id": 0},
    {"title": None},
    {"title": "  "},
    {"url": 123},
    {"rules_url": None},
    {"rules_url": "  "},
    {"task_type": "unknown"},
    {"country": ""},
    {"eligibility": "maybe"},
    {"terms_verified": 1},
    {"automated_agents_allowed": "yes"},
    {"official_api": None},
    {"allowed_actions": ["submit_entry"]},
    {"allowed_actions": ("submit_entry", "submit_entry")},
    {"allowed_actions": ("bad action",)},
])
def test_competition_rejects_malformed_metadata(changes):
    with pytest.raises(ValueError):
        competition(**changes)


def test_competition_ready_only_when_all_automation_gates_are_met():
    assert assess_competition(competition()).ready
    result = assess_competition(competition(terms_verified=False))
    assert not result.ready
    assert "rules have not been manually verified" in " ".join(result.blockers)


@pytest.mark.parametrize("changes", [
    {"eligibility": "unknown"},
    {"eligibility": "ineligible"},
    {"automated_agents_allowed": False},
    {"official_api": False},
    {"allowed_actions": ()},
    {"url": "http://contest.example.com/event"},
])
def test_competition_blocks_unverified_or_unsupported_automation(changes):
    assert not assess_competition(competition(**changes)).ready


def test_strategy_is_transparent_and_task_specific():
    plan = build_strategy(1, "coding", "Solve within 2 seconds")
    assert plan.provider == "heuristic-baseline"
    assert plan.task_type == "coding"
    assert any("complexity" in check.lower() for check in plan.validation_checks)
    assert plan.confidence < 100


def test_strategy_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        build_strategy(0, "logic")
    with pytest.raises(ValueError):
        build_strategy(1, "unknown")


class FakeAdapter:
    manifest = CompetitionAdapterManifest(
        adapter_id="example-official", exact_host="contest.example.com",
        official_api=True, automated_agents_allowed=True,
        allowed_actions=("submit_entry",),
    )

    def __init__(self):
        self.calls = 0

    def submit_entry(self, competition, payload):
        self.calls += 1
        return SubmissionReceipt("entry-123", "accepted", "official API receipt")


@pytest.mark.parametrize("confirmation", ["yes", 1, None, [], {}])
def test_submission_rejects_truthy_or_malformed_owner_confirmation(confirmation):
    registry = CompetitionAdapterRegistry()
    adapter = FakeAdapter()
    registry.register(adapter)
    with pytest.raises(PermissionError, match="owner confirmation"):
        registry.submit("example-official", competition(), {"answer": 42}, owner_confirmed=confirmation)
    assert adapter.calls == 0


def test_submission_rejects_malformed_adapter_id_and_competition():
    registry = CompetitionAdapterRegistry()
    adapter = FakeAdapter()
    registry.register(adapter)
    with pytest.raises(ValueError, match="adapter_id"):
        registry.submit([], competition(), {"answer": 42}, owner_confirmed=True)
    with pytest.raises(TypeError, match="Competition instance"):
        registry.submit("example-official", {}, {"answer": 42}, owner_confirmed=True)
    assert adapter.calls == 0


def test_submission_requires_owner_confirmation_and_exact_registered_adapter():
    registry = CompetitionAdapterRegistry()
    adapter = FakeAdapter()
    registry.register(adapter)
    with pytest.raises(PermissionError, match="owner confirmation"):
        registry.submit("example-official", competition(), {"answer": 42}, owner_confirmed=False)
    with pytest.raises(PermissionError, match="exact allowlist"):
        registry.submit("example-official", competition(url="https://sub.contest.example.com/event"),
                        {"answer": 42}, owner_confirmed=True)
    receipt = registry.submit("example-official", competition(), {"answer": 42}, owner_confirmed=True)
    assert receipt.external_entry_id == "entry-123"
    assert adapter.calls == 1


def test_unknown_adapter_cannot_submit():
    with pytest.raises(KeyError, match="not registered"):
        CompetitionAdapterRegistry().submit(
            "missing", competition(), {"answer": 42}, owner_confirmed=True
        )


def test_registry_rejects_adapter_without_callable_submit_method():
    class IncompleteAdapter:
        manifest = CompetitionAdapterManifest(
            adapter_id="incomplete-adapter", exact_host="contest.example.com",
            official_api=True, automated_agents_allowed=True,
            allowed_actions=("submit_entry",),
        )

    registry = CompetitionAdapterRegistry()
    with pytest.raises(TypeError, match="callable submit_entry"):
        registry.register(IncompleteAdapter())
    assert registry.get_manifest("incomplete-adapter") is None


def test_manifest_rejects_wildcard_and_unapproved_adapter():
    with pytest.raises(ValueError):
        CompetitionAdapterManifest(
            adapter_id="wild", exact_host="*.example.com",
            official_api=True, automated_agents_allowed=True,
            allowed_actions=("submit_entry",),
        )
    with pytest.raises(ValueError):
        CompetitionAdapterManifest(
            adapter_id="not-approved", exact_host="contest.example.com",
            official_api=True, automated_agents_allowed=False,
            allowed_actions=("submit_entry",),
        )

def test_configured_openai_responses_provider_builds_validated_strategy(monkeypatch):
    import json
    from autoearn import competitions

    expected = {
        "approach": "Reason carefully and verify",
        "steps": ["Parse the rules", "Solve the task", "Check the answer"],
        "validation_checks": ["Check legality", "Check output format"],
        "fallback": "Abstain if uncertain",
        "confidence": 62,
    }

    class FakeResponse:
        status = 200

        def read(self, limit):
            return json.dumps({
                "output": [{
                    "type": "message",
                    "content": [{
                        "type": "output_text",
                        "text": json.dumps(expected),
                    }],
                }]
            }).encode("utf-8")

    captured = {}

    class FakeConnection:
        def __init__(self, host, timeout, context):
            captured["host"] = host
            captured["timeout"] = timeout

        def request(self, method, path, body, headers):
            captured["method"] = method
            captured["path"] = path
            captured["authorization"] = headers["Authorization"]

        def getresponse(self):
            return FakeResponse()

        def close(self):
            captured["closed"] = True

    monkeypatch.setenv("AUTOEARN_OPENAI_API_KEY", "test-only-secret")
    monkeypatch.setenv("AUTOEARN_OPENAI_MODEL", "test-model")
    monkeypatch.setattr(competitions.http.client, "HTTPSConnection", FakeConnection)

    plan = competitions.build_strategy(3, "logic", "Find the winning answer")
    assert plan.provider == "test-model"
    assert plan.confidence == 62
    assert len(plan.steps) == 3
    assert captured["host"] == "api.openai.com"
    assert captured["path"] == "/v1/responses"
    assert captured["method"] == "POST"
    assert captured["authorization"] == "Bearer test-only-secret"
    assert captured["timeout"] == 30
    assert captured["closed"] is True


def test_configured_ai_provider_rejects_invalid_model_output(monkeypatch):
    import json
    from autoearn import competitions

    class FakeResponse:
        status = 200

        def read(self, limit):
            return json.dumps({"output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": '{"approach":"bad"}'}],
            }]}).encode("utf-8")

    class FakeConnection:
        def __init__(self, host, timeout, context):
            pass

        def request(self, method, path, body, headers):
            pass

        def getresponse(self):
            return FakeResponse()

        def close(self):
            pass

    monkeypatch.setenv("AUTOEARN_OPENAI_API_KEY", "test-only-secret")
    monkeypatch.setattr(competitions.http.client, "HTTPSConnection", FakeConnection)
    with pytest.raises(competitions.AIProviderError, match="invalid strategy format"):
        competitions.build_strategy(4, "coding")


def test_competition_adapter_enforces_manifest_requests_per_minute(monkeypatch):
    from autoearn import competitions as module

    class LimitedAdapter(FakeAdapter):
        manifest = CompetitionAdapterManifest(
            adapter_id="limited-official", exact_host="contest.example.com",
            official_api=True, automated_agents_allowed=True,
            allowed_actions=("submit_entry",), requests_per_minute=1,
        )

    clock = {"value": 100.0}
    monkeypatch.setattr(module, "monotonic", lambda: clock["value"])
    registry = CompetitionAdapterRegistry()
    adapter = LimitedAdapter()
    registry.register(adapter)

    first = registry.submit(
        "limited-official", competition(), {"answer": 1}, owner_confirmed=True
    )
    assert first.status == "accepted"
    with pytest.raises(PermissionError, match="rate limit exceeded"):
        registry.submit(
            "limited-official", competition(), {"answer": 2}, owner_confirmed=True
        )
    assert adapter.calls == 1

    clock["value"] += 60
    second = registry.submit(
        "limited-official", competition(), {"answer": 3}, owner_confirmed=True
    )
    assert second.status == "accepted"
    assert adapter.calls == 2



@pytest.mark.parametrize("url", [
    "https://user:password@contest.example.com/event",
    "https://contest.example.com:8443/event",
    "https://contest.example.com/event#fragment",
    "https://contest.example.com:bad/event",
])
def test_competition_rejects_ambiguous_or_credential_bearing_urls(url):
    assert not assess_competition(competition(url=url)).ready


def test_competition_rejects_unsafe_rules_url():
    result = assess_competition(competition(
        rules_url="https://user:secret@contest.example.com/rules"
    ))
    assert not result.ready
    assert any("rules URL" in blocker for blocker in result.blockers)


@pytest.mark.parametrize("payload", [
    {"answer": float("nan")},
    {"answer": object()},
    {"answer": "آ" * 11000},
    {1: "answer"},
])
def test_submission_rejects_non_json_or_oversized_payload(payload):
    registry = CompetitionAdapterRegistry()
    adapter = FakeAdapter()
    registry.register(adapter)
    with pytest.raises(ValueError, match="payload"):
        registry.submit(
            "example-official", competition(), payload, owner_confirmed=True
        )
    assert adapter.calls == 0


def test_submission_rejects_cyclic_payload_without_calling_adapter():
    registry = CompetitionAdapterRegistry()
    adapter = FakeAdapter()
    registry.register(adapter)
    cyclic = []
    cyclic.append(cyclic)

    with pytest.raises(ValueError, match="payload"):
        registry.submit(
            "example-official", competition(), {"answer": cyclic}, owner_confirmed=True
        )
    assert adapter.calls == 0


def test_submission_rejects_excessively_nested_payload_without_calling_adapter():
    registry = CompetitionAdapterRegistry()
    adapter = FakeAdapter()
    registry.register(adapter)
    nested = "leaf"
    for _ in range(1500):
        nested = [nested]

    with pytest.raises(ValueError, match="payload"):
        registry.submit(
            "example-official", competition(), {"answer": nested}, owner_confirmed=True
        )
    assert adapter.calls == 0


@pytest.mark.parametrize("receipt", [
    SubmissionReceipt("", "accepted"),
    SubmissionReceipt("entry-" + "x" * 300, "accepted"),
    SubmissionReceipt("entry-1", "Accepted"),
    SubmissionReceipt("entry-1", "accepted\nforged"),
    SubmissionReceipt("entry-1\x7f", "accepted"),
    SubmissionReceipt("entry-1", "accepted", "evidence\x85text"),
    SubmissionReceipt("entry-1", "accepted", "x" * 2001),
])
def test_submission_rejects_malformed_adapter_receipts(receipt):
    class BadReceiptAdapter(FakeAdapter):
        def submit_entry(self, competition, payload):
            self.calls += 1
            return receipt

    registry = CompetitionAdapterRegistry()
    adapter = BadReceiptAdapter()
    registry.register(adapter)
    with pytest.raises(RuntimeError, match="invalid submission receipt"):
        registry.submit(
            "example-official", competition(), {"answer": 42}, owner_confirmed=True
        )


@pytest.mark.parametrize("changes", [
    {"adapter_id": None},
    {"adapter_id": "Bad Adapter"},
    {"exact_host": None},
    {"exact_host": " contest.example.com "},
    {"exact_host": "x" * 254},
    {"official_api": 1},
    {"automated_agents_allowed": "yes"},
    {"allowed_actions": ["submit_entry"]},
    {"allowed_actions": ("submit_entry", "submit_entry")},
    {"allowed_actions": ("SubmitEntry",)},
    {"allowed_actions": ("../submit",)},
    {"requests_per_minute": True},
    {"requests_per_minute": 1.5},
])
def test_competition_manifest_rejects_malformed_fields(changes):
    values = dict(
        adapter_id="safe-adapter",
        exact_host="contest.example.com",
        official_api=True,
        automated_agents_allowed=True,
        allowed_actions=("submit_entry",),
    )
    values.update(changes)
    with pytest.raises(ValueError):
        CompetitionAdapterManifest(**values)


@pytest.mark.parametrize("host", [
    "127.0.0.1", "10.0.0.8", "192.168.1.1", "::1", "2001:db8::1",
    "::ffff:127.0.0.1",
])
def test_competition_manifest_rejects_ip_address_hosts(host):
    with pytest.raises(ValueError, match="public DNS hostname"):
        CompetitionAdapterManifest(
            adapter_id="ip-host",
            exact_host=host,
            official_api=True,
            automated_agents_allowed=True,
            allowed_actions=("submit_entry",),
        )


def test_competition_manifest_accepts_valid_bounded_configuration():
    manifest = CompetitionAdapterManifest(
        adapter_id="safe_adapter-1",
        exact_host="contest.example.com",
        official_api=True,
        automated_agents_allowed=True,
        allowed_actions=("submit_entry", "check_status"),
        requests_per_minute=5,
    )
    assert manifest.adapter_id == "safe_adapter-1"
    assert manifest.requests_per_minute == 5


def test_registry_pins_manifest_snapshot_at_registration():
    class MutableManifestAdapter:
        def __init__(self):
            self.current_manifest = CompetitionAdapterManifest(
                adapter_id="pinned-adapter",
                exact_host="contest.example.com",
                official_api=True,
                automated_agents_allowed=True,
                allowed_actions=("submit_entry",),
            )
            self.calls = 0

        @property
        def manifest(self):
            return self.current_manifest

        def submit_entry(self, competition, payload):
            self.calls += 1
            return SubmissionReceipt("pinned-entry", "accepted")

    adapter = MutableManifestAdapter()
    registry = CompetitionAdapterRegistry()
    registry.register(adapter)

    adapter.current_manifest = CompetitionAdapterManifest(
        adapter_id="pinned-adapter",
        exact_host="attacker.example.net",
        official_api=True,
        automated_agents_allowed=True,
        allowed_actions=("submit_entry",),
    )

    assert registry.get_manifest("pinned-adapter").exact_host == "contest.example.com"
    receipt = registry.submit(
        "pinned-adapter", competition(), {"answer": 7}, owner_confirmed=True
    )
    assert receipt.external_entry_id == "pinned-entry"
    assert adapter.calls == 1

@pytest.mark.parametrize("response_body", [
    [],
    {"output": {}},
    {"output": ["not-an-item"]},
    {"output": [{"type": "message", "content": {}}]},
    {"output": [{"type": "message", "content": ["not-a-part"]}]},
])
def test_configured_ai_provider_rejects_malformed_response_envelopes(
    monkeypatch, response_body
):
    import json
    from autoearn import competitions

    class FakeResponse:
        status = 200

        def read(self, limit):
            return json.dumps(response_body).encode("utf-8")

    class FakeConnection:
        def __init__(self, host, timeout, context):
            pass

        def request(self, method, path, body, headers):
            pass

        def getresponse(self):
            return FakeResponse()

        def close(self):
            pass

    monkeypatch.setenv("AUTOEARN_OPENAI_API_KEY", "test-only-secret")
    monkeypatch.setattr(competitions.http.client, "HTTPSConnection", FakeConnection)
    with pytest.raises(competitions.AIProviderError, match="invalid response format"):
        competitions.build_strategy(5, "logic")

