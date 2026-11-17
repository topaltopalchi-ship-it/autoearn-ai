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
