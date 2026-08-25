from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Answer, AnswerTypeEnum, Assignment, Attempt, MoodleSubmission, MoodleUserLink, RoleEnum, User
from app.services.processing import process_answer_uploaded
from app.tests.conftest import auth_header, register_and_login


def _enable_moodle(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "moodle_integration_enabled", True)
    monkeypatch.setattr(settings, "moodle_integration_token", "moodle-secret")
    monkeypatch.setattr(settings, "moodle_integration_site_id", "test-moodle")
    monkeypatch.setattr(settings, "moodle_integration_owner_emails", [])
    return {
        "X-TuneAI-Integration-Key": "moodle-secret",
        "X-TuneAI-Moodle-Site": "test-moodle",
    }


def _create_published_test(client):
    admin_token = register_and_login(client, "admin@example.com")
    return _create_published_test_for_token(client, admin_token)


def _create_published_test_for_token(client, token, title="Moodle oral checkpoint"):
    response = client.post(
        "/tests",
        headers=auth_header(token),
        json={
            "title": title,
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
    published = client.patch(f"/tests/{response.json()['id']}", headers=auth_header(token), json={"status": "published"})
    assert published.status_code == 200, published.text
    return published.json()


def _create_staff_user(client, admin_token, email, role="methodist"):
    response = client.post(
        "/users",
        headers=auth_header(admin_token),
        json={"email": email, "full_name": "Moodle Owner", "password": "password123", "role": role},
    )
    assert response.status_code == 201, response.text
    login = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


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

    monkeypatch.setattr(settings, "moodle_integration_site_id", "trusted-moodle")
    wrong_site = client.post(
        "/integrations/moodle/submissions/text",
        headers={
            "X-TuneAI-Integration-Key": "moodle-secret",
            "X-TuneAI-Moodle-Site": "another-moodle",
        },
        json=payload,
    )
    assert wrong_site.status_code == 401
    assert wrong_site.json()["detail"] == "Moodle site identifier is not trusted"


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
        "moodle_group_id": "group-3",
        "moodle_group_name": "PI-101",
        "methodist_email": "admin@example.com",
        "user_email": "student42@example.edu",
        "user_full_name": "Moodle Student",
        "test_id": test["id"],
        "question_id": question_id,
        "text": "Transactional outbox writes event data atomically with business changes.",
    }

    submitted = client.post("/integrations/moodle/submissions/text", headers=headers, json=payload)
    assert submitted.status_code == 201, submitted.text
    body = submitted.json()
    assert body["moodle_site_id"] == "test-moodle"
    assert body["answer_status"] == "queued_for_transcription"
    assert body["result_ready"] is False
    assert body["max_score"] == 10
    assert body["moodle_course_id"] == "course-10"
    assert body["moodle_activity_id"] == "quiz-7"
    assert body["moodle_group_id"] == "group-3"
    assert body["moodle_group_name"] == "PI-101"
    assert body["methodist_email"] == "admin@example.com"
    assert body["test_id"] == test["id"]
    assert body["question_id"] == question_id

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
            "moodle_group_id": "group-audio",
            "moodle_group_name": "Voice group",
            "methodist_email": "admin@example.com",
            "user_email": "speaker55@example.edu",
            "user_full_name": "Speaker Student",
            "test_id": test["id"],
            "question_id": test["questions"][0]["id"],
        },
        files={"file": ("answer.webm", b"\x1a\x45\xdf\xa3fake audio bytes", "audio/webm")},
    )
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["moodle_group_id"] == "group-audio"
    with SessionLocal() as db:
        answer = db.get(Answer, submitted.json()["answer_id"])
        assert answer is not None
        assert answer.answer_type == AnswerTypeEnum.audio
        assert answer.audio_object_key


def test_moodle_manifest_filters_published_tests_by_methodist(client, monkeypatch):
    headers = _enable_moodle(monkeypatch)
    admin_token = register_and_login(client, "admin@example.com")
    first_methodist_token = _create_staff_user(client, admin_token, "methodist.one@example.edu")
    second_methodist_token = _create_staff_user(client, admin_token, "methodist.two@example.edu")
    first_test = _create_published_test_for_token(client, first_methodist_token, "First methodist exam")
    _create_published_test_for_token(client, second_methodist_token, "Second methodist exam")

    response = client.get(
        "/integrations/moodle/manifest",
        headers=headers,
        params={"methodist_email": "methodist.one@example.edu"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [test["id"] for test in body["tests"]] == [first_test["id"]]
    assert body["tests"][0]["owner_email"] == "methodist.one@example.edu"
    assert body["tests"][0]["questions"][0]["id"] == first_test["questions"][0]["id"]
    assert body["tests"][0]["questions"][0]["answer_mode"] == "both"


def test_moodle_submission_respects_question_answer_mode(client, monkeypatch):
    headers = _enable_moodle(monkeypatch)
    admin_token = register_and_login(client, "admin@example.com")
    created = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Moodle mixed modes",
            "test_type": "exam",
            "questions": [
                {
                    "text": "Voice-only Moodle question?",
                    "expected_answer": "Audio answer.",
                    "answer_mode": "audio",
                    "order_index": 0,
                    "max_score": 10,
                },
                {
                    "text": "Text-only Moodle question?",
                    "expected_answer": "Text answer.",
                    "answer_mode": "text",
                    "order_index": 1,
                    "max_score": 10,
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    published = client.patch(f"/tests/{created.json()['id']}", headers=auth_header(admin_token), json={"status": "published"})
    assert published.status_code == 200, published.text
    test = published.json()

    blocked_text = client.post(
        "/integrations/moodle/submissions/text",
        headers=headers,
        json={
            "external_submission_id": "moodle-mode-text-blocked",
            "moodle_user_id": "42",
            "user_email": "student42@example.edu",
            "user_full_name": "Moodle Student",
            "methodist_email": "admin@example.com",
            "test_id": test["id"],
            "question_id": test["questions"][0]["id"],
            "text": "Trying text for an audio question.",
        },
    )
    assert blocked_text.status_code == 403
    assert blocked_text.json()["detail"] == "Text answers are disabled for this question"

    blocked_audio = client.post(
        "/integrations/moodle/submissions/audio",
        headers=headers,
        data={
            "external_submission_id": "moodle-mode-audio-blocked",
            "moodle_user_id": "43",
            "methodist_email": "admin@example.com",
            "user_email": "student43@example.edu",
            "user_full_name": "Moodle Student",
            "test_id": test["id"],
            "question_id": test["questions"][1]["id"],
        },
        files={"file": ("answer.webm", b"\x1a\x45\xdf\xa3fake audio bytes", "audio/webm")},
    )
    assert blocked_audio.status_code == 403
    assert blocked_audio.json()["detail"] == "Audio answers are disabled for this question"


def test_moodle_submission_rejects_wrong_methodist_scope(client, monkeypatch):
    headers = _enable_moodle(monkeypatch)
    test = _create_published_test(client)
    payload = {
        "external_submission_id": "wrong-methodist-submission",
        "moodle_user_id": "42",
        "user_email": "student42@example.edu",
        "user_full_name": "Moodle Student",
        "methodist_email": "other-owner@example.edu",
        "test_id": test["id"],
        "question_id": test["questions"][0]["id"],
        "text": "This should not be accepted for another methodist.",
    }

    response = client.post("/integrations/moodle/submissions/text", headers=headers, json=payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "Test does not belong to the requested methodist"


def test_moodle_retake_creates_a_new_attempt_for_the_same_question(client, monkeypatch):
    headers = _enable_moodle(monkeypatch)
    test = _create_published_test(client)
    base = {
        "moodle_user_id": "retake-user",
        "user_email": "retake@example.edu",
        "user_full_name": "Retake Student",
        "test_id": test["id"],
        "question_id": test["questions"][0]["id"],
        "text": "The event is stored atomically and published later.",
    }

    first = client.post(
        "/integrations/moodle/submissions/text",
        headers=headers,
        json={**base, "external_submission_id": "retake-1", "external_attempt_id": "quiz-attempt-1"},
    )
    second = client.post(
        "/integrations/moodle/submissions/text",
        headers=headers,
        json={**base, "external_submission_id": "retake-2", "external_attempt_id": "quiz-attempt-2"},
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["attempt_id"] != second.json()["attempt_id"]
    assert first.json()["answer_id"] != second.json()["answer_id"]


def test_moodle_identity_is_stable_when_email_changes(client, monkeypatch):
    headers = _enable_moodle(monkeypatch)
    test = _create_published_test(client)
    base = {
        "moodle_user_id": "stable-user-42",
        "user_full_name": "Stable Student",
        "test_id": test["id"],
        "question_id": test["questions"][0]["id"],
        "text": "Transactional outbox answer.",
    }
    first = client.post(
        "/integrations/moodle/submissions/text",
        headers=headers,
        json={
            **base,
            "external_submission_id": "identity-1",
            "external_attempt_id": "identity-attempt-1",
            "user_email": "old-address@example.edu",
        },
    )
    second = client.post(
        "/integrations/moodle/submissions/text",
        headers=headers,
        json={
            **base,
            "external_submission_id": "identity-2",
            "external_attempt_id": "identity-attempt-2",
            "user_email": "new-address@example.edu",
        },
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    with SessionLocal() as db:
        first_submission = db.scalar(select(MoodleSubmission).where(MoodleSubmission.external_submission_id == "identity-1"))
        second_submission = db.scalar(select(MoodleSubmission).where(MoodleSubmission.external_submission_id == "identity-2"))
        link = db.scalar(select(MoodleUserLink).where(MoodleUserLink.moodle_user_id == "stable-user-42"))
        assert first_submission.user_id == second_submission.user_id == link.user_id
        assert link.email == "new-address@example.edu"


def test_moodle_rejects_collision_with_staff_identity(client, monkeypatch):
    headers = _enable_moodle(monkeypatch)
    test = _create_published_test(client)
    response = client.post(
        "/integrations/moodle/submissions/text",
        headers=headers,
        json={
            "external_submission_id": "staff-collision",
            "moodle_user_id": "staff-user",
            "user_email": "admin@example.com",
            "user_full_name": "Moodle Admin Collision",
            "test_id": test["id"],
            "question_id": test["questions"][0]["id"],
            "text": "Must not attach to a TuneAI administrator.",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Moodle email is already used by another TuneAI identity"

    admin_token = register_and_login(client, "admin@example.com")
    native = client.post(
        "/users",
        headers=auth_header(admin_token),
        json={
            "email": "native-examinee@example.edu",
            "full_name": "Native Examinee",
            "password": "password123",
            "role": "examinee",
        },
    )
    assert native.status_code == 201, native.text
    native_collision = client.post(
        "/integrations/moodle/submissions/text",
        headers=headers,
        json={
            "external_submission_id": "native-collision",
            "moodle_user_id": "native-user",
            "user_email": "native-examinee@example.edu",
            "user_full_name": "Moodle Native Collision",
            "test_id": test["id"],
            "question_id": test["questions"][0]["id"],
            "text": "Must not attach to a native TuneAI examinee.",
        },
    )
    assert native_collision.status_code == 409


def test_moodle_manual_review_clears_signal_and_sets_final_result(client, monkeypatch):
    headers = _enable_moodle(monkeypatch)
    test = _create_published_test(client)
    payload = {
        "external_submission_id": "manual-review-submission",
        "external_attempt_id": "manual-review-attempt",
        "moodle_user_id": "review-user",
        "user_email": "review-user@example.edu",
        "user_full_name": "Review Student",
        "test_id": test["id"],
        "question_id": test["questions"][0]["id"],
        "text": "The outbox transaction stores the event and data together.",
    }
    submitted = client.post("/integrations/moodle/submissions/text", headers=headers, json=payload)
    assert submitted.status_code == 201, submitted.text
    with SessionLocal() as db:
        awaitable_process(db, submitted.json()["answer_id"])

    reviewed = client.post(
        "/integrations/moodle/submissions/manual-review-submission/review",
        headers=headers,
        json={
            "score": 8.5,
            "feedback": "Approved by the Moodle teacher.",
            "reviewer_moodle_user_id": "7",
            "reviewer_name": "Moodle Teacher",
        },
    )

    assert reviewed.status_code == 200, reviewed.text
    body = reviewed.json()
    assert body["score"] == 8.5
    assert body["feedback"] == "Approved by the Moodle teacher."
    assert body["review_required"] is False
    assert body["review_reason"] is None
    assert body["teacher_signal"] == "none"
    with SessionLocal() as db:
        submission = db.scalar(select(MoodleSubmission).where(MoodleSubmission.external_submission_id == "manual-review-submission"))
        attempt = db.get(Attempt, submission.attempt_id)
        assert submission.reviewer_moodle_user_id == "7"
        assert submission.reviewer_name == "Moodle Teacher"
        assert attempt.total_score == 8.5


def test_moodle_owner_allowlist_scopes_manifest_and_submissions(client, monkeypatch):
    headers = _enable_moodle(monkeypatch)
    test = _create_published_test(client)
    monkeypatch.setattr(get_settings(), "moodle_integration_owner_emails", ["allowed@example.edu"])

    manifest = client.get("/integrations/moodle/manifest", headers=headers)
    assert manifest.status_code == 200
    assert manifest.json()["tests"] == []

    response = client.post(
        "/integrations/moodle/submissions/text",
        headers=headers,
        json={
            "external_submission_id": "owner-not-allowed",
            "moodle_user_id": "owner-scope-user",
            "user_email": "owner-scope@example.edu",
            "user_full_name": "Owner Scope Student",
            "test_id": test["id"],
            "question_id": test["questions"][0]["id"],
            "text": "This owner is outside the integration allowlist.",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Test owner is not allowed for Moodle integration"


def awaitable_process(db, answer_id):
    import asyncio

    return asyncio.run(process_answer_uploaded(db, answer_id=answer_id))
