from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Answer, AnswerTypeEnum, Assignment, MoodleSubmission, RoleEnum, User
from app.services.processing import process_answer_uploaded
from app.tests.conftest import auth_header, register_and_login


def _enable_moodle(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "moodle_integration_enabled", True)
    monkeypatch.setattr(settings, "moodle_integration_token", "moodle-secret")
    return {"X-TuneAI-Integration-Key": "moodle-secret"}


def _create_published_test(client):
    admin_token = register_and_login(client, "admin@example.com")
    response = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Moodle oral checkpoint",
            "test_type": "exam",
            "questions": [
                {
                    "text": "Explain transactional outbox.",
                    "expected_answer": "Atomic event publishing with business data.",
                    "max_score": 10,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    published = client.patch(f"/tests/{response.json()['id']}", headers=auth_header(admin_token), json={"status": "published"})
    assert published.status_code == 200, published.text
    return published.json()


def test_moodle_integration_requires_enabled_token(client, monkeypatch):
    test = _create_published_test(client)
    payload = {
        "external_submission_id": "sub-disabled",
        "moodle_user_id": "42",
        "user_email": "student42@example.edu",
        "user_full_name": "Moodle Student",
        "test_id": test["id"],
        "question_id": test["questions"][0]["id"],
        "text": "The outbox stores an event in the same transaction.",
    }
    disabled = client.post("/integrations/moodle/submissions/text", json=payload)
    assert disabled.status_code == 404
    assert disabled.json()["detail"] == "Moodle integration is disabled"

    settings = get_settings()
    monkeypatch.setattr(settings, "moodle_integration_enabled", True)
    monkeypatch.setattr(settings, "moodle_integration_token", "moodle-secret")
    invalid = client.post("/integrations/moodle/submissions/text", headers={"X-TuneAI-Integration-Key": "bad"}, json=payload)
    assert invalid.status_code == 401


def test_moodle_text_submission_replays_and_returns_teacher_signal(client, monkeypatch):
    headers = _enable_moodle(monkeypatch)
    test = _create_published_test(client)
    question_id = test["questions"][0]["id"]
    payload = {
        "external_submission_id": "assign-7-user-42-question-1",
        "external_attempt_id": "quiz-attempt-7-user-42",
        "moodle_user_id": "42",
        "moodle_course_id": "course-10",
        "moodle_activity_id": "quiz-7",
        "user_email": "student42@example.edu",
        "user_full_name": "Moodle Student",
        "test_id": test["id"],
        "question_id": question_id,
        "text": "Transactional outbox writes event data atomically with business changes.",
    }

    submitted = client.post("/integrations/moodle/submissions/text", headers=headers, json=payload)
    assert submitted.status_code == 201, submitted.text
    body = submitted.json()
    assert body["answer_status"] == "queued_for_transcription"
    assert body["result_ready"] is False
    assert body["max_score"] == 10

    replay = client.post("/integrations/moodle/submissions/text", headers=headers, json={**payload, "text": "Different text"})
    assert replay.status_code == 201
    assert replay.json()["answer_id"] == body["answer_id"]

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "student42@example.edu"))
        assert user is not None
        assert user.role == RoleEnum.examinee
        assignment = db.scalar(select(Assignment).where(Assignment.test_id == test["id"], Assignment.user_id == user.id))
        assert assignment is not None
        submission = db.scalar(select(MoodleSubmission).where(MoodleSubmission.external_submission_id == payload["external_submission_id"]))
        assert submission is not None
        processed = awaitable_process(db, body["answer_id"])
        assert processed.status.value == "completed"

    result = client.get(f"/integrations/moodle/submissions/{payload['external_submission_id']}/result", headers=headers)
    assert result.status_code == 200
    result_body = result.json()
    assert result_body["result_ready"] is True
    assert result_body["score"] is not None
    assert result_body["grade"] is not None
    assert result_body["review_required"] is True
    assert result_body["teacher_signal"] == "review_recommended"
    assert result_body["feedback"]


def test_moodle_audio_submission_creates_audio_answer(client, monkeypatch):
    headers = _enable_moodle(monkeypatch)
    test = _create_published_test(client)
    submitted = client.post(
        "/integrations/moodle/submissions/audio",
        headers=headers,
        data={
            "external_submission_id": "audio-sub-1",
            "external_attempt_id": "audio-attempt-1",
            "moodle_user_id": "55",
            "user_email": "speaker55@example.edu",
            "user_full_name": "Speaker Student",
            "test_id": test["id"],
            "question_id": test["questions"][0]["id"],
        },
        files={"file": ("answer.webm", b"fake audio bytes", "audio/webm")},
    )
    assert submitted.status_code == 201, submitted.text
    with SessionLocal() as db:
        answer = db.get(Answer, submitted.json()["answer_id"])
        assert answer is not None
        assert answer.answer_type == AnswerTypeEnum.audio
        assert answer.audio_object_key


def awaitable_process(db, answer_id):
    import asyncio

    return asyncio.run(process_answer_uploaded(db, answer_id=answer_id))
