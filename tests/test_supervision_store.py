import pytest

from autoearn.supervision import SupervisionError
from autoearn.supervision_store import SQLiteSupervisionStore


def make_store(tmp_path):
    return SQLiteSupervisionStore(tmp_path / "agent.sqlite3")


def create(store, action="submit_application"):
    return store.create(
        opportunity_id=5,
        action=action,
        description="Submit an application after user review",
        opportunity_eligible=True,
        source_approved=True,
        evidence_fresh=True,
    )


def test_requests_and_audit_survive_store_recreation(tmp_path):
    db_path = tmp_path / "persist.sqlite3"
    store = SQLiteSupervisionStore(db_path)
    request = create(store)
    store = SQLiteSupervisionStore(db_path)
    loaded = store.get(request.request_id)
    assert loaded is not None
    assert loaded.status == "pending_approval"
    assert [event.event_type for event in store.audit_events(request.request_id)] == ["requested"]


def test_approval_and_completion_are_persisted_with_audit(tmp_path):
    store = make_store(tmp_path)
    request = create(store)
    assert store.approve(request.request_id, actor="owner").status == "approved"
    assert store.complete(request.request_id, actor="owner", evidence="Submission receipt #123").status == "completed"
    assert [e.event_type for e in store.audit_events(request.request_id)] == [
        "requested", "approved", "marked_completed"
    ]
    assert store.get(request.request_id).completed_at


def test_reject_and_cancel_transitions_are_enforced(tmp_path):
    store = make_store(tmp_path)
    rejected = create(store)
    store.reject(rejected.request_id, actor="owner", reason="Not worthwhile")
    with pytest.raises(SupervisionError):
        store.approve(rejected.request_id, actor="owner")

    cancelled = create(store)
    store.cancel(cancelled.request_id, actor="owner", reason="Stop")
    with pytest.raises(SupervisionError):
        store.complete(cancelled.request_id, actor="owner", evidence="receipt")


def test_creation_requires_eligibility_source_approval_and_fresh_evidence(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(SupervisionError):
        store.create(
            opportunity_id=5, action="prepare_draft", description="Draft",
            opportunity_eligible=False, source_approved=True, evidence_fresh=True,
        )


def test_decision_requires_human_actor_and_completion_evidence(tmp_path):
    store = make_store(tmp_path)
    request = create(store)
    with pytest.raises(SupervisionError, match="human actor"):
        store.approve(request.request_id, actor="system")
    store.approve(request.request_id, actor="owner")
    with pytest.raises(SupervisionError, match="evidence"):
        store.complete(request.request_id, actor="owner", evidence=" ")


def test_concurrent_decisions_allow_only_one_transition(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    store = make_store(tmp_path)
    request = create(store)
    barrier = Barrier(2)

    def decide(method):
        barrier.wait()
        try:
            method(request.request_id, actor="owner")
            return "success"
        except SupervisionError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(decide, [store.approve, store.reject]))

    assert sorted(outcomes) == ["rejected", "success"]
    final = store.get(request.request_id)
    assert final.status in {"approved", "rejected"}
    decisions = [event for event in store.audit_events(request.request_id)
                 if event.event_type in {"approved", "rejected"}]
    assert len(decisions) == 1


def test_case_variant_system_actor_is_rejected_for_all_decisions(tmp_path):
    store = make_store(tmp_path)
    request = create(store)
    with pytest.raises(SupervisionError, match="human actor"):
        store.approve(request.request_id, actor="SYSTEM")
    with pytest.raises(SupervisionError, match="human actor"):
        store.reject(request.request_id, actor=" System ")
    store.approve(request.request_id, actor="owner")
    with pytest.raises(SupervisionError, match="human actor"):
        store.complete(request.request_id, actor="SYSTEM", evidence="receipt")
    with pytest.raises(SupervisionError, match="human actor"):
        store.cancel(request.request_id, actor=" System ")


@pytest.mark.parametrize("opportunity_id", [True, False, 0, -1, 1.5, "5"])
def test_creation_requires_positive_integer_opportunity_id(tmp_path, opportunity_id):
    store = make_store(tmp_path)
    with pytest.raises(SupervisionError, match="opportunity_id"):
        store.create(
            opportunity_id=opportunity_id, action="prepare_draft", description="Draft",
            opportunity_eligible=True, source_approved=True, evidence_fresh=True,
        )


@pytest.mark.parametrize("actor", [None, "", "   ", 123])
def test_creation_rejects_missing_or_invalid_request_actor(tmp_path, actor):
    store = make_store(tmp_path)
    with pytest.raises(SupervisionError, match="actor"):
        store.create(
            opportunity_id=5, action="prepare_draft", description="Draft",
            opportunity_eligible=True, source_approved=True, evidence_fresh=True,
            actor=actor,
        )


@pytest.mark.parametrize("flag", ["yes", 1, None])
@pytest.mark.parametrize("field", ["opportunity_eligible", "source_approved", "evidence_fresh"])
def test_creation_requires_literal_true_readiness_flags(tmp_path, field, flag):
    store = make_store(tmp_path)
    flags = {"opportunity_eligible": True, "source_approved": True, "evidence_fresh": True}
    flags[field] = flag
    with pytest.raises(SupervisionError, match="eligible"):
        store.create(opportunity_id=5, action="prepare_draft", description="Draft", **flags)


def test_status_filter_rejects_unknown_or_non_string_values(tmp_path):
    store = make_store(tmp_path)
    create(store)
    for status in ("unknown", "", 1, []):
        with pytest.raises(SupervisionError, match="status"):
            store.list(status=status)


@pytest.mark.parametrize("value", [None, 123, []])
def test_transition_rejects_non_text_evidence_and_reason(tmp_path, value):
    store = make_store(tmp_path)
    request = create(store)
    store.approve(request.request_id, actor="owner")
    with pytest.raises(SupervisionError, match="evidence"):
        store.complete(request.request_id, actor="owner", evidence=value)
    with pytest.raises(SupervisionError, match="reason"):
        store.reject(request.request_id, actor="owner", reason=value)
    with pytest.raises(SupervisionError, match="reason"):
        store.cancel(request.request_id, actor="owner", reason=value)


def test_audit_events_follow_commit_order_when_wall_clock_moves_backwards(tmp_path, monkeypatch):
    import autoearn.supervision_store as store_module

    store = make_store(tmp_path)
    stamps = iter(("2026-11-18T12:00:00+00:00", "2026-11-18T12:00:02+00:00", "2026-11-18T12:00:03+00:00", "2026-11-18T12:00:01+00:00"))
    monkeypatch.setattr(store_module, "_timestamp", lambda: next(stamps))

    request = create(store)
    store.approve(request.request_id, actor="owner")

    events = store.audit_events(request.request_id)
    assert [event.event_type for event in events] == ["requested", "approved"]
    assert [event.occurred_at for event in events] == list(("2026-11-18T12:00:02+00:00", "2026-11-18T12:00:01+00:00"))

