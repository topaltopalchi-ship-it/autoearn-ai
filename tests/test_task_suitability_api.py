def test_task_suitability_assessment_api_is_owner_only_and_never_authorizes_execution(client):
    from app import main

    payload = {
        "title": "Format public catalog data",
        "ai_permission": "allowed",
        "repetitive_information_processing": True,
        "output_is_objectively_verifiable": True,
    }
    assert client.post("/api/task-suitability/assess", json=payload).status_code == 401

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    response = client.post("/api/task-suitability/assess", headers=headers, json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["suitability"] == "ai_draft_candidate"
    assert result["score"] == 85
    assert result["execution_authorized"] is False

    unknown = client.post("/api/task-suitability/assess", headers=headers, json={
        "title": "Unclear task rules",
    })
    assert unknown.status_code == 200
    assert unknown.json()["suitability"] == "manual_policy_review"
    assert unknown.json()["execution_authorized"] is False

    prohibited = client.post("/api/task-suitability/assess", headers=headers, json={
        "title": "Platform prohibits AI",
        "ai_permission": "prohibited",
    })
    assert prohibited.status_code == 200
    assert prohibited.json()["suitability"] == "blocked"
    assert prohibited.json()["execution_authorized"] is False
