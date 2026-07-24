import pytest

from app.db.session import SessionLocal
from app.models import Answer, OutboxEvent, OutboxStatusEnum
from app.services.processing import process_answer_uploaded
from app.tests.conftest import auth_header, register_and_login


def create_sample_test(client, token):
    response = client.post(
        "/tests",
        headers=auth_header(token),
        json={
            "title": "Distributed systems oral exam",
            "description": "Checks queue, broker, and transaction knowledge.",
            "test_type": "self_training",
            "criteria": {"rubric": "Grade correctness, completeness, and argumentation."},
            "questions": [
                {
                    "text": "Explain why a transactional outbox is useful.",
                    "expected_answer": "The answer should mention atomic database writes and reliable event publishing.",
                    "order_index": 0,
                    "max_score": 10,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    test = response.json()
    published = client.patch(
        f"/tests/{test['id']}",
        headers=auth_header(token),
        json={"status": "published"},
    )
    assert published.status_code == 200, published.text
    return published.json()


def create_two_question_test(client, token):
    response = client.post(
        "/tests",
        headers=auth_header(token),
        json={
            "title": "Hidden questions exam",
            "description": "Questions should unlock one by one.",
            "test_type": "self_training",
            "questions": [
                {
                    "text": "First revealed question?",
                    "expected_answer": "First rubric hint.",
                    "order_index": 0,
                    "max_score": 10,
                },
                {
                    "text": "Second hidden question?",
                    "expected_answer": "Second rubric hint.",
                    "order_index": 1,
                    "max_score": 10,
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    test = response.json()
    published = client.patch(
        f"/tests/{test['id']}",
        headers=auth_header(token),
        json={"status": "published"},
    )
    assert published.status_code == 200, published.text
    return published.json()


@pytest.mark.asyncio
async def test_audio_upload_creates_outbox_event_and_processing_completes(client):
    admin_token = register_and_login(client, "admin@example.com")
    test = create_sample_test(client, admin_token)

    material = client.post(
        "/materials",
        headers=auth_header(admin_token),
        json={
            "test_id": test["id"],
            "title": "Lecture notes",
            "content": "Transactional outbox stores business changes and integration events in one database transaction. "
            "A publisher then sends pending events to a message broker and marks them as published.",
        },
    )
    assert material.status_code == 201, material.text

    attempt_response = client.post(
        "/attempts",
        headers=auth_header(admin_token),
        json={"test_id": test["id"]},
    )
    assert attempt_response.status_code == 201, attempt_response.text
    attempt = attempt_response.json()

    upload = client.post(
        f"/attempts/{attempt['id']}/questions/{test['questions'][0]['id']}/audio",
        headers=auth_header(admin_token),
        files={"file": ("answer.webm", b"fake webm audio bytes", "audio/webm")},
    )
    assert upload.status_code == 201, upload.text
    answer = upload.json()["answers"][0]
    assert answer["status"] == "queued_for_transcription"

    with SessionLocal() as db:
        outbox = db.query(OutboxEvent).one()
        assert outbox.status == OutboxStatusEnum.pending
        processed = await process_answer_uploaded(db, answer_id=answer["id"])
        assert processed.status.value == "completed"

    result = client.get(f"/attempts/{attempt['id']}", headers=auth_header(admin_token))
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "completed"
    assert payload["answers"][0]["transcript"]
    assert payload["answers"][0]["evaluation"]["confidence"] >= 0

    dashboard = client.get("/admin/dashboard", headers=auth_header(admin_token))
    assert dashboard.status_code == 200
    assert dashboard.json()["attempts"] == 1
    assert dashboard.json()["answers_completed"] == 1

    admin_attempts = client.get("/admin/attempts", headers=auth_header(admin_token))
    assert admin_attempts.status_code == 200
    assert admin_attempts.json()[0]["test_title"] == "Distributed systems oral exam"

    failed_jobs = client.get("/admin/failed-jobs", headers=auth_header(admin_token))
    assert failed_jobs.status_code == 200
    assert failed_jobs.json() == []


def test_questions_are_hidden_until_attempt_reveals_them(client):
    admin_token = register_and_login(client, "admin@example.com")
    test = create_two_question_test(client, admin_token)
    first_question_id = test["questions"][0]["id"]
    second_question_id = test["questions"][1]["id"]

    student_token = register_and_login(client, "student@example.com")
    visible_tests = client.get("/tests", headers=auth_header(student_token))
    assert visible_tests.status_code == 200
    student_test = visible_tests.json()[0]
    assert student_test["question_count"] == 2
    assert student_test["questions"] == []

    attempt_response = client.post(
        "/attempts",
        headers=auth_header(student_token),
        json={"test_id": test["id"]},
    )
    assert attempt_response.status_code == 201, attempt_response.text
    attempt = attempt_response.json()
    assert [question["id"] for question in attempt["questions"]] == [first_question_id]
    assert "expected_answer" not in attempt["questions"][0]

    premature_upload = client.post(
        f"/attempts/{attempt['id']}/questions/{second_question_id}/audio",
        headers=auth_header(student_token),
        files={"file": ("answer.webm", b"fake webm audio bytes", "audio/webm")},
    )
    assert premature_upload.status_code == 403
    assert premature_upload.json()["detail"] == "Question is not revealed yet"

    first_upload = client.post(
        f"/attempts/{attempt['id']}/questions/{first_question_id}/audio",
        headers=auth_header(student_token),
        files={"file": ("answer.webm", b"fake webm audio bytes", "audio/webm")},
    )
    assert first_upload.status_code == 201, first_upload.text
    assert [question["id"] for question in first_upload.json()["questions"]] == [first_question_id, second_question_id]


def test_examinee_sees_only_assigned_exam_and_no_public_self_training(client):
    admin_token = register_and_login(client, "admin@example.com")
    self_training = create_two_question_test(client, admin_token)
    exam_response = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Assigned exam",
            "test_type": "exam",
            "questions": [{"text": "Explain the outbox?", "max_score": 10}],
        },
    )
    assert exam_response.status_code == 201, exam_response.text
    exam = exam_response.json()
    published_exam = client.patch(
        f"/tests/{exam['id']}",
        headers=auth_header(admin_token),
        json={"status": "published"},
    )
    assert published_exam.status_code == 200, published_exam.text

    created_user = client.post(
        "/users",
        headers=auth_header(admin_token),
        json={
            "email": "examinee@example.com",
            "full_name": "Exam Taker",
            "password": "password123",
            "role": "examinee",
        },
    )
    assert created_user.status_code == 201, created_user.text
    examinee = created_user.json()
    examinee_token = register_and_login(client, "examinee@example.com")

    before_assignment = client.get("/tests", headers=auth_header(examinee_token))
    assert before_assignment.status_code == 200
    assert before_assignment.json() == []

    forbidden_attempt = client.post(
        "/attempts",
        headers=auth_header(examinee_token),
        json={"test_id": self_training["id"]},
    )
    assert forbidden_attempt.status_code == 403

    assigned = client.post(
        f"/tests/{exam['id']}/assign",
        headers=auth_header(admin_token),
        json={"user_id": examinee["id"]},
    )
    assert assigned.status_code == 204, assigned.text

    after_assignment = client.get("/tests", headers=auth_header(examinee_token))
    assert after_assignment.status_code == 200
    assigned_tests = after_assignment.json()
    assert [item["title"] for item in assigned_tests] == ["Assigned exam"]
    assert assigned_tests[0]["questions"] == []

    attempt_response = client.post(
        "/attempts",
        headers=auth_header(examinee_token),
        json={"test_id": exam["id"]},
    )
    assert attempt_response.status_code == 201, attempt_response.text
    assert attempt_response.json()["questions"][0]["text"] == "Explain the outbox?"


def test_user_cannot_read_another_users_attempt(client):
    admin_token = register_and_login(client, "admin@example.com")
    test = create_sample_test(client, admin_token)
    first_student = register_and_login(client, "student-a@example.com")
    second_student = register_and_login(client, "student-b@example.com")

    first_attempt = client.post(
        "/attempts",
        headers=auth_header(first_student),
        json={"test_id": test["id"]},
    )
    assert first_attempt.status_code == 201, first_attempt.text

    forbidden = client.get(
        f"/attempts/{first_attempt.json()['id']}",
        headers=auth_header(second_student),
    )
    assert forbidden.status_code == 403

    allowed = client.get(
        f"/attempts/{first_attempt.json()['id']}",
        headers=auth_header(first_student),
    )
    assert allowed.status_code == 200
