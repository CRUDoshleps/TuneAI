from datetime import datetime, timedelta, timezone
import json

from app.db.session import SessionLocal
from app.models import Material, OutboxEvent, Question, Test as DbTest, User
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
    assert response.json()["config"]["demoBootstrapEnabled"] is True


def test_public_config_demo_capability_cannot_be_overridden_by_branding_json(client, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("DEMO_BOOTSTRAP_ENABLED", "false")
    monkeypatch.setenv("NEXT_PUBLIC_TUNEAI_CONFIG_JSON", '{"demoBootstrapEnabled": true}')
    try:
        response = client.get("/public/config")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["config"]["demoBootstrapEnabled"] is False


def test_public_config_ignores_blank_runtime_brand_values(client, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("NEXT_PUBLIC_TUNEAI_PRODUCT_NAME", "")
    monkeypatch.setenv("NEXT_PUBLIC_TUNEAI_LOGO_TEXT", "")
    monkeypatch.setenv("NEXT_PUBLIC_TUNEAI_LOGO_URL", "")
    try:
        response = client.get("/public/config")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()["config"]
    assert payload["productName"] == "Self-host Test Platform"
    assert payload["logoText"] == "Demo"
    assert payload["logoUrl"] is None


def test_public_config_exposes_brand_theme_from_env_and_json(client, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("NEXT_PUBLIC_TUNEAI_ACCENT_COLOR", "#1fbf75")
    monkeypatch.setenv("NEXT_PUBLIC_TUNEAI_BACKGROUND_COLOR", "#f7fbf2")
    monkeypatch.setenv(
        "NEXT_PUBLIC_TUNEAI_CONFIG_JSON",
        json.dumps(
            {
                "productName": "Faculty Trainer",
                "theme": {
                    "accent": "#ff0000",
                    "panel": "#ffffff",
                    "line": "#c7d8c2",
                },
            }
        ),
    )
    try:
        response = client.get("/public/config")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()["config"]
    assert payload["productName"] == "Faculty Trainer"
    assert payload["theme"] == {
        "accent": "#1fbf75",
        "background": "#f7fbf2",
        "panel": "#ffffff",
        "line": "#c7d8c2",
    }


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
        assert db.query(Question).filter(Question.test_id == payload["test"]["id"]).count() == 0
        assert db.query(Material).filter(Material.test_id == payload["test"]["id"]).count() == 0
        assert db.query(Material).filter(Material.owner_id == payload["user"]["id"]).count() == 0


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
