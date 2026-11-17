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
