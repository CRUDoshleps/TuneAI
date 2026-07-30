from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models import OutboxEvent, Test as DbTest, User
from app.services.demo_cleanup import cleanup_expired_demo_data
from app.services.outbox import MATERIAL_UPLOADED
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
    assert payload["user"]["is_demo"] is True
    assert payload["user"]["expires_at"]
    assert payload["test"]["test_type"] == "exam"
    assert payload["test"]["is_demo"] is True
    assert payload["test"]["questions"] == []

    tests = client.get("/tests", headers=auth_header(payload["tokens"]["access_token"]))
    assert tests.status_code == 200
    assert [item["id"] for item in tests.json()] == [payload["test"]["id"]]
    attempt = client.post("/attempts", headers=auth_header(payload["tokens"]["access_token"]), json={"test_id": payload["test"]["id"]})
    assert attempt.status_code == 201, attempt.text
    assert attempt.json()["questions"][0]["competencies"] == [{"name": "Фактическая точность", "weight": 1.0}]

    with SessionLocal() as db:
        material_event = db.query(OutboxEvent).filter(OutboxEvent.event_type == MATERIAL_UPLOADED).one()
        assert material_event.payload["test_id"] == payload["test"]["id"]


def test_demo_cleanup_removes_expired_demo_users_and_tests(client):
    response = client.post(
        "/public/demo/bootstrap",
        json={
            "scenario_id": "self-training",
            "label": "Самоподготовка",
            "test_type": "self_training",
            "role_label": "Студент",
            "title": "Self demo",
            "description": "Training",
            "question": "Explain RAG.",
            "expected_answer": "Retrieval augmented generation.",
            "agent_profile": "self-training-mentor",
            "competencies": ["RAG"],
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    with SessionLocal() as db:
        user = db.get(User, payload["user"]["id"])
        test = db.get(DbTest, payload["test"]["id"])
        assert user is not None
        assert test is not None
        user.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        test.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.add(user)
        db.add(test)
        db.commit()
        removed = cleanup_expired_demo_data(db)
        assert removed == 2
        assert db.get(User, payload["user"]["id"]) is None
        assert db.get(DbTest, payload["test"]["id"]) is None


def test_demo_bootstrap_limit_can_block_new_demo_users(client, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("DEMO_BOOTSTRAP_LIMIT_PER_HOUR", "0")
    try:
        response = client.post(
            "/public/demo/bootstrap",
            json={
                "scenario_id": "blocked-demo",
                "label": "Blocked",
                "test_type": "exam",
                "role_label": "Экзаменуемый",
                "title": "Blocked demo",
                "description": "Blocked",
                "question": "Explain outbox.",
                "expected_answer": "Atomic event publishing.",
                "agent_profile": "exam-strict-reviewer",
                "competencies": ["Reliability"],
            },
        )
    finally:
        monkeypatch.delenv("DEMO_BOOTSTRAP_LIMIT_PER_HOUR", raising=False)
        get_settings.cache_clear()

    assert response.status_code == 429
    assert response.json()["detail"] == "Demo bootstrap limit exceeded"
