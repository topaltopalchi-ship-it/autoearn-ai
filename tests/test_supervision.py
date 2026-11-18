import pytest

from autoearn.supervision import SupervisionError, SupervisionQueue


def create(queue, action="prepare_draft"):
    return queue.create(
        opportunity_id=12,
        action=action,
        description="Prepare the application draft",
        opportunity_eligible=True,
        source_approved=True,
        evidence_fresh=True,
    )


@pytest.mark.parametrize("kwargs", [
    {"opportunity_eligible": False, "source_approved": True, "evidence_fresh": True},
    {"opportunity_eligible": True, "source_approved": False, "evidence_fresh": True},
    {"opportunity_eligible": True, "source_approved": True, "evidence_fresh": False},
])
def test_request_requires_eligible_approved_and_fresh_opportunity(kwargs):
    queue = SupervisionQueue()
    with pytest.raises(SupervisionError):
        queue.create(
            opportunity_id=1, action="prepare_draft", description="Draft",
            **kwargs,
        )


def test_action_requires_explicit_human_approval_before_completion():
    queue = SupervisionQueue()
    request = create(queue)
    with pytest.raises(SupervisionError, match="only approved"):
        queue.complete(request.request_id, actor="user", evidence="receipt")
    approved = queue.approve(request.request_id, actor="user")
    assert approved.status == "approved"
    completed = queue.complete(request.request_id, actor="user", evidence="Manual completion confirmed")
    assert completed.status == "completed"
    assert len(queue.audit_events(request.request_id)) == 3


def test_sensitive_actions_are_never_auto_approved():
    queue = SupervisionQueue()
    request = create(queue, action="withdraw_funds")
    assert request.status == "pending_approval"
    assert request.approved_at is None
    assert queue.audit_events(request.request_id)[0].event_type == "requested"


def test_approval_requires_human_actor():
    queue = SupervisionQueue()
    request = create(queue)
    with pytest.raises(SupervisionError, match="human actor"):
        queue.approve(request.request_id, actor="system")


def test_rejected_and_cancelled_requests_cannot_be_completed():
    queue = SupervisionQueue()
    rejected = create(queue)
    queue.reject(rejected.request_id, actor="user", reason="Not suitable")
    with pytest.raises(SupervisionError):
        queue.approve(rejected.request_id, actor="user")

    cancelled = create(queue)
    queue.cancel(cancelled.request_id, actor="user", reason="Stop")
    with pytest.raises(SupervisionError):
        queue.approve(cancelled.request_id, actor="user")


def test_completion_requires_evidence():
    queue = SupervisionQueue()
    request = create(queue)
    queue.approve(request.request_id, actor="user")
    with pytest.raises(SupervisionError, match="evidence"):
        queue.complete(request.request_id, actor="user", evidence=" ")


@pytest.mark.parametrize("actor", ["", "   ", "system", " system ", "SYSTEM", " System "])
def test_completion_requires_human_actor(actor):
    queue = SupervisionQueue()
    request = create(queue)
    queue.approve(request.request_id, actor="owner")
    with pytest.raises(SupervisionError, match="human actor"):
        queue.complete(request.request_id, actor=actor, evidence="receipt")


@pytest.mark.parametrize("actor", ["", "   ", "system", " system ", "SYSTEM", " System "])
def test_cancellation_requires_human_actor(actor):
    queue = SupervisionQueue()
    request = create(queue)
    with pytest.raises(SupervisionError, match="human actor"):
        queue.cancel(request.request_id, actor=actor)


def test_concurrent_approvals_allow_exactly_one_transition():
    from concurrent.futures import ThreadPoolExecutor

    queue = SupervisionQueue()
    request = create(queue)

    def approve(actor):
        try:
            queue.approve(request.request_id, actor=actor)
            return "approved"
        except SupervisionError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(approve, ("owner-a", "owner-b")))

    assert sorted(outcomes) == ["approved", "rejected"]
    assert queue.get(request.request_id).status == "approved"
    assert [event.event_type for event in queue.audit_events(request.request_id)] == [
        "requested", "approved"
    ]


@pytest.mark.parametrize("opportunity_id", [True, False, 0, -1, "12", 1.5])
def test_create_rejects_non_positive_integer_opportunity_ids(opportunity_id):
    queue = SupervisionQueue()
    with pytest.raises(SupervisionError, match="positive integer"):
        queue.create(
            opportunity_id=opportunity_id, action="prepare_draft", description="Draft",
            opportunity_eligible=True, source_approved=True, evidence_fresh=True,
        )


@pytest.mark.parametrize("actor", ["", "   ", None, 7])
def test_create_requires_valid_actor(actor):
    queue = SupervisionQueue()
    with pytest.raises(SupervisionError, match="actor"):
        queue.create(
            opportunity_id=1, action="prepare_draft", description="Draft", actor=actor,
            opportunity_eligible=True, source_approved=True, evidence_fresh=True,
        )


@pytest.mark.parametrize("flag", [1, "true", None])
def test_create_requires_actual_boolean_readiness_flags(flag):
    queue = SupervisionQueue()
    with pytest.raises(SupervisionError, match="eligible"):
        queue.create(
            opportunity_id=1, action="prepare_draft", description="Draft",
            opportunity_eligible=flag, source_approved=True, evidence_fresh=True,
        )


def test_get_rejects_invalid_request_id_type():
    queue = SupervisionQueue()
    with pytest.raises(SupervisionError, match="request_id"):
        queue.get([])
