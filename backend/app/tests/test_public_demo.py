from app.tests.conftest import auth_header


def test_public_config_uses_runtime_environment(client, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("NEXT_PUBLIC_TUNEAI_PRODUCT_NAME", "Campus Oral AI")
    monkeypatch.setenv("NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL", "help@example.com")
    try:
        response = client.get("/public/config")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["config"]["productName"] == "Campus Oral AI"
    assert response.json()["config"]["consultationEmail"] == "help@example.com"


def test_demo_bootstrap_creates_assigned_exam_for_examinee(client):
    response = client.post(
        "/public/demo/bootstrap",
        json={
            "scenario_id": "oral-exam",
            "label": "Устный экзамен",
            "test_type": "exam",
            "role_label": "Экзаменуемый",
            "title": "Exam demo",
            "description": "Assigned exam",
            "question": "Explain transactional outbox.",
            "expected_answer": "Atomic write and publish.",
            "agent_profile": "exam-strict-reviewer",
            "competencies": ["Фактическая точность"],
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["user"]["role"] == "examinee"
    assert payload["test"]["test_type"] == "exam"

    tests = client.get("/tests", headers=auth_header(payload["tokens"]["access_token"]))
    assert tests.status_code == 200
    assert [item["id"] for item in tests.json()] == [payload["test"]["id"]]
