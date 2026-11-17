import pytest

from autoearn.task_suitability import TaskProfile, assess_task_suitability


def test_unknown_ai_permission_requires_policy_review():
    result = assess_task_suitability(TaskProfile("Research summary"))
    assert result.suitability == "manual_policy_review"
    assert result.execution_authorized is False


def test_explicitly_prohibited_ai_is_blocked():
    result = assess_task_suitability(TaskProfile("Survey", ai_permission="prohibited"))
    assert result.suitability == "blocked"
    assert result.score == 0


@pytest.mark.parametrize("flag", [
    "requires_physical_presence",
    "requires_personal_experience",
    "requires_identity_attestation",
    "requires_captcha",
    "requires_live_human_interaction",
])
def test_human_only_requirements_cannot_be_replaced_by_ai(flag):
    result = assess_task_suitability(
        TaskProfile("Human task", ai_permission="allowed", **{flag: True})
    )
    assert result.suitability == "human_only"
    assert result.execution_authorized is False


def test_repetitive_verifiable_work_is_only_an_ai_draft_candidate():
    result = assess_task_suitability(TaskProfile(
        "Format public catalog data",
        ai_permission="allowed",
        repetitive_information_processing=True,
        output_is_objectively_verifiable=True,
    ))
    assert result.suitability == "ai_draft_candidate"
    assert result.score == 85
    assert result.execution_authorized is False
    assert "human reviews" in result.permitted_ai_role


def test_sensitive_data_requires_privacy_review_even_if_ai_is_allowed():
    result = assess_task_suitability(TaskProfile(
        "Process customer records",
        ai_permission="allowed",
        contains_sensitive_personal_data=True,
        repetitive_information_processing=True,
        output_is_objectively_verifiable=True,
    ))
    assert result.suitability == "ai_assisted_human_review"
    assert result.score == 25


def test_partial_ai_fit_remains_human_reviewed():
    result = assess_task_suitability(TaskProfile(
        "Draft a proposal",
        ai_permission="allowed",
        output_is_objectively_verifiable=True,
    ))
    assert result.suitability == "ai_assisted_human_review"
    assert result.execution_authorized is False


def test_invalid_profile_is_rejected():
    with pytest.raises(ValueError, match="title"):
        TaskProfile(" ")
    with pytest.raises(ValueError, match="ai_permission"):
        TaskProfile("Task", ai_permission="maybe")
    with pytest.raises(ValueError, match="boolean"):
        TaskProfile("Task", requires_captcha="no")
