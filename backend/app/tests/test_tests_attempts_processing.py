import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Answer, AnswerStatusEnum, Material, OutboxEvent, OutboxStatusEnum
from app.schemas import EvaluationResult
from app.services.outbox import ANSWER_UPLOADED, MATERIAL_UPLOADED
from app.services.processing import process_answer_uploaded
from app.services.rag import index_material
from app.tests.conftest import auth_header, register_and_login


class RecordingAI:
    def __init__(self):
        from app.core.config import get_settings

        self.settings = get_settings()
        self.skill_instructions = ""

    async def transcribe_audio(self, audio: bytes, content_type: str | None) -> str:
        return "Recorded transcript"

    async def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2]

    async def embed_document(self, text: str) -> list[float]:
        return [0.1, 0.2]

    async def evaluate_answer(self, **kwargs):
        self.skill_instructions = kwargs.get("ai_skill_instructions", "")
        return EvaluationResult(
            score=8,
            max_score=kwargs["max_score"],
            correct_points=["Uses the configured skill."],
            feedback="Skill-aware feedback.",
            recommendations="Keep using concrete terms.",
            confidence=0.9,
        )


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


def assign_test_to_current_user(client, manager_token, target_token, test_id):
    target = client.get("/auth/me", headers=auth_header(target_token))
    assert target.status_code == 200, target.text
    assigned = client.post(
        f"/tests/{test_id}/assign",
        headers=auth_header(manager_token),
        json={"user_id": target.json()["id"]},
    )
    assert assigned.status_code == 204, assigned.text


async def index_test_materials(test_id: str) -> None:
    with SessionLocal() as db:
        material_ids = list(db.scalars(select(Material.id).where(Material.test_id == test_id)).all())
        for material_id in material_ids:
            await index_material(db, material_id)


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
    assert material.json()["index_status"] == "uploaded"
    await index_test_materials(test["id"])

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
        outbox = db.scalar(select(OutboxEvent).where(OutboxEvent.event_type == ANSWER_UPLOADED))
        assert outbox is not None
        assert outbox.status == OutboxStatusEnum.pending
        processed = await process_answer_uploaded(db, answer_id=answer["id"])
        assert processed.status.value == "completed"

    result = client.get(f"/attempts/{attempt['id']}", headers=auth_header(admin_token))
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "completed"
    assert payload["answers"][0]["transcript"]
    assert payload["answers"][0]["evaluation"]["confidence"] >= 0
    assert payload["answers"][0]["evaluation"]["grounded"] is True
    assert payload["answers"][0]["evaluation"]["source_excerpts"]
    assert payload["answers"][0]["evaluation"]["review_recommended"] is True
    assert payload["answers"][0]["evaluation"]["evaluation_version"] == "tuneai-rubric-v1"

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


@pytest.mark.asyncio
async def test_teacher_reviews_low_confidence_answer_and_overrides_attempt_total(client):
    admin_token = register_and_login(client, "admin@example.com")
    teacher_response = client.post(
        "/users",
        headers=auth_header(admin_token),
        json={
            "email": "teacher@example.com",
            "full_name": "Review Teacher",
            "password": "password123",
            "role": "teacher",
        },
    )
    assert teacher_response.status_code == 201, teacher_response.text
    teacher_token = register_and_login(client, "teacher@example.com")
    test = create_sample_test(client, teacher_token)
    material = client.post(
        "/materials",
        headers=auth_header(teacher_token),
        json={
            "test_id": test["id"],
            "title": "Review material",
            "content": "Transactional outbox atomically saves an event with business data before publishing it.",
        },
    )
    assert material.status_code == 201, material.text
    await index_test_materials(test["id"])

    student_response = client.post(
        "/users",
        headers=auth_header(teacher_token),
        json={
            "email": "student@example.com",
            "full_name": "Managed Student",
            "password": "password123",
            "role": "student",
        },
    )
    assert student_response.status_code == 201, student_response.text
    student_token = register_and_login(client, "student@example.com")
    assign_test_to_current_user(client, teacher_token, student_token, test["id"])
    attempt_response = client.post(
        "/attempts",
        headers=auth_header(student_token),
        json={"test_id": test["id"]},
    )
    assert attempt_response.status_code == 201, attempt_response.text
    attempt = attempt_response.json()
    upload = client.post(
        f"/attempts/{attempt['id']}/questions/{test['questions'][0]['id']}/audio",
        headers=auth_header(student_token),
        files={"file": ("answer.webm", b"fake webm audio bytes", "audio/webm;codecs=opus")},
    )
    assert upload.status_code == 201, upload.text
    answer_id = upload.json()["answers"][0]["id"]
    with SessionLocal() as db:
        await process_answer_uploaded(db, answer_id=answer_id)

    forbidden_queue = client.get("/attempts/review-queue", headers=auth_header(student_token))
    assert forbidden_queue.status_code == 403

    queue = client.get("/attempts/review-queue", headers=auth_header(teacher_token))
    assert queue.status_code == 200, queue.text
    assert len(queue.json()) == 1
    assert queue.json()[0]["answer_id"] == answer_id
    assert queue.json()[0]["confidence"] == 0.72

    excessive = client.patch(
        f"/attempts/{attempt['id']}/answers/{answer_id}/review",
        headers=auth_header(teacher_token),
        json={"score": 11, "feedback": "Too high"},
    )
    assert excessive.status_code == 422
    assert excessive.json()["detail"] == "Review score exceeds maximum"

    reviewed = client.patch(
        f"/attempts/{attempt['id']}/answers/{answer_id}/review",
        headers=auth_header(teacher_token),
        json={"score": 7.5, "feedback": "Зачтено после проверки преподавателем."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["review_score"] == 7.5
    assert reviewed.json()["reviewed_by_id"] == teacher_response.json()["id"]
    assert reviewed.json()["reviewed_at"]

    student_result = client.get(f"/attempts/{attempt['id']}", headers=auth_header(student_token))
    assert student_result.status_code == 200
    assert student_result.json()["total_score"] == 7.5
    assert student_result.json()["answers"][0]["review_feedback"].startswith("Зачтено")

    history = client.get("/attempts", headers=auth_header(student_token))
    assert history.status_code == 200
    assert history.json()[0]["id"] == attempt["id"]
    assert history.json()[0]["answers"][0]["review_score"] == 7.5

    empty_queue = client.get("/attempts/review-queue", headers=auth_header(teacher_token))
    assert empty_queue.status_code == 200
    assert empty_queue.json() == []


def test_questions_are_hidden_until_attempt_reveals_them(client):
    admin_token = register_and_login(client, "admin@example.com")
    test = create_two_question_test(client, admin_token)
    first_question_id = test["questions"][0]["id"]
    second_question_id = test["questions"][1]["id"]

    student_token = register_and_login(client, "student@example.com")
    assign_test_to_current_user(client, admin_token, student_token, test["id"])
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
    result_before_answer = client.get(f"/attempts/{attempt['id']}/result", headers=auth_header(student_token))
    assert result_before_answer.status_code == 200
    assert [question["id"] for question in result_before_answer.json()["questions"]] == [first_question_id]

    premature_upload = client.post(
        f"/attempts/{attempt['id']}/questions/{second_question_id}/audio",
        headers=auth_header(student_token),
        files={"file": ("answer.webm", b"fake webm audio bytes", "audio/webm")},
    )
    assert premature_upload.status_code == 403
    assert premature_upload.json()["detail"] == "Question is not revealed yet"

    first_upload = client.post(
        f"/attempts/{attempt['id']}/questions/{first_question_id}/audio",
        headers={**auth_header(student_token), "Idempotency-Key": "first-audio-answer"},
        files={"file": ("answer.webm", b"fake webm audio bytes", "audio/webm")},
    )
    assert first_upload.status_code == 201, first_upload.text
    assert [question["id"] for question in first_upload.json()["questions"]] == [first_question_id, second_question_id]
    replay = client.post(
        f"/attempts/{attempt['id']}/questions/{first_question_id}/audio",
        headers={**auth_header(student_token), "Idempotency-Key": "first-audio-answer"},
        files={"file": ("answer.webm", b"fake webm audio bytes", "audio/webm")},
    )
    assert replay.status_code == 201
    assert replay.json()["answers"][0]["id"] == first_upload.json()["answers"][0]["id"]


def test_question_answer_modes_control_text_and_audio_submission(client):
    admin_token = register_and_login(client, "admin@example.com")
    created = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Mixed answer modes exam",
            "description": "Each question defines the allowed answer format.",
            "test_type": "self_training",
            "questions": [
                {
                    "text": "Answer this question by voice only.",
                    "expected_answer": "Voice answer.",
                    "answer_mode": "audio",
                    "order_index": 0,
                    "max_score": 10,
                },
                {
                    "text": "Answer this question as written text only.",
                    "expected_answer": "Written answer.",
                    "answer_mode": "text",
                    "order_index": 1,
                    "max_score": 10,
                },
                {
                    "text": "Answer this question using either text or voice.",
                    "expected_answer": "Flexible answer.",
                    "answer_mode": "both",
                    "order_index": 2,
                    "max_score": 10,
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    test = created.json()
    assert [question["answer_mode"] for question in test["questions"]] == ["audio", "text", "both"]

    published = client.patch(f"/tests/{test['id']}", headers=auth_header(admin_token), json={"status": "published"})
    assert published.status_code == 200, published.text
    attempt_response = client.post("/attempts", headers=auth_header(admin_token), json={"test_id": test["id"]})
    assert attempt_response.status_code == 201, attempt_response.text
    attempt = attempt_response.json()
    assert [question["answer_mode"] for question in attempt["questions"]] == ["audio", "text", "both"]

    audio_only_id = test["questions"][0]["id"]
    text_only_id = test["questions"][1]["id"]
    flexible_id = test["questions"][2]["id"]

    blocked_text = client.post(
        f"/attempts/{attempt['id']}/questions/{audio_only_id}/text",
        headers=auth_header(admin_token),
        json={"text": "Trying to submit text."},
    )
    assert blocked_text.status_code == 403
    assert blocked_text.json()["detail"] == "Text answers are disabled for this question"

    allowed_audio = client.post(
        f"/attempts/{attempt['id']}/questions/{audio_only_id}/audio",
        headers=auth_header(admin_token),
        files={"file": ("answer.webm", b"fake webm audio bytes", "audio/webm")},
    )
    assert allowed_audio.status_code == 201, allowed_audio.text
    answers_by_question = {answer["question_id"]: answer for answer in allowed_audio.json()["answers"]}
    assert answers_by_question[audio_only_id]["answer_type"] == "audio"

    blocked_audio = client.post(
        f"/attempts/{attempt['id']}/questions/{text_only_id}/audio",
        headers=auth_header(admin_token),
        files={"file": ("answer.webm", b"fake webm audio bytes", "audio/webm")},
    )
    assert blocked_audio.status_code == 403
    assert blocked_audio.json()["detail"] == "Audio answers are disabled for this question"

    allowed_text = client.post(
        f"/attempts/{attempt['id']}/questions/{text_only_id}/text",
        headers=auth_header(admin_token),
        json={"text": "Submitting the required written answer."},
    )
    assert allowed_text.status_code == 201, allowed_text.text
    answers_by_question = {answer["question_id"]: answer for answer in allowed_text.json()["answers"]}
    assert answers_by_question[text_only_id]["answer_type"] == "text"

    flexible_text = client.post(
        f"/attempts/{attempt['id']}/questions/{flexible_id}/text",
        headers=auth_header(admin_token),
        json={"text": "This mode accepts text too."},
    )
    assert flexible_text.status_code == 201, flexible_text.text
    answers_by_question = {answer["question_id"]: answer for answer in flexible_text.json()["answers"]}
    assert answers_by_question[flexible_id]["answer_type"] == "text"


def test_student_does_not_see_unassigned_published_self_training(client):
    admin_token = register_and_login(client, "admin@example.com")
    test = create_two_question_test(client, admin_token)
    student_token = register_and_login(client, "student@example.com")

    visible_tests = client.get("/tests", headers=auth_header(student_token))
    assert visible_tests.status_code == 200
    assert visible_tests.json() == []

    direct_read = client.get(f"/tests/{test['id']}", headers=auth_header(student_token))
    assert direct_read.status_code == 403

    forbidden_attempt = client.post(
        "/attempts",
        headers=auth_header(student_token),
        json={"test_id": test["id"]},
    )
    assert forbidden_attempt.status_code == 403
    assert forbidden_attempt.json()["detail"] == "Test is not assigned to this user"


def test_admin_can_delete_material_and_empty_test(client):
    admin_token = register_and_login(client, "admin@example.com")
    test = create_sample_test(client, admin_token)
    material = client.post(
        "/materials",
        headers=auth_header(admin_token),
        json={
            "test_id": test["id"],
            "title": "Temporary notes",
            "content": "This material is long enough to be accepted and then removed by an administrator.",
        },
    )
    assert material.status_code == 201, material.text

    removed_material = client.delete(f"/materials/{material.json()['id']}", headers=auth_header(admin_token))
    assert removed_material.status_code == 204, removed_material.text
    materials = client.get(f"/materials?test_id={test['id']}", headers=auth_header(admin_token))
    assert materials.status_code == 200
    assert materials.json() == []

    attempted = client.post(
        "/attempts",
        headers=auth_header(admin_token),
        json={"test_id": test["id"]},
    )
    assert attempted.status_code == 201, attempted.text
    archived_delete = client.delete(f"/tests/{test['id']}", headers=auth_header(admin_token))
    assert archived_delete.status_code == 204
    archived = client.get(f"/tests/{test['id']}", headers=auth_header(admin_token))
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    empty_test = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Draft to delete",
            "test_type": "self_training",
            "questions": [{"text": "Can this be removed?", "max_score": 10}],
        },
    )
    assert empty_test.status_code == 201, empty_test.text
    deleted = client.delete(f"/tests/{empty_test.json()['id']}", headers=auth_header(admin_token))
    assert deleted.status_code == 204, deleted.text
    missing = client.get(f"/tests/{empty_test.json()['id']}", headers=auth_header(admin_token))
    assert missing.status_code == 404


def test_materials_can_be_bound_to_specific_question_and_attempt_result_api(client):
    admin_token = register_and_login(client, "admin@example.com")
    test = create_two_question_test(client, admin_token)
    first_question_id = test["questions"][0]["id"]
    second_question_id = test["questions"][1]["id"]

    general_material = client.post(
        "/materials",
        headers=auth_header(admin_token),
        json={
            "test_id": test["id"],
            "title": "General notes",
            "content": "General notes that apply to the whole oral scenario and every answer.",
        },
    )
    assert general_material.status_code == 201, general_material.text
    scoped_material = client.post(
        "/materials",
        headers=auth_header(admin_token),
        json={
            "test_id": test["id"],
            "question_id": first_question_id,
            "title": "First question notes",
            "content": "Specific notes for the first question only and its grading context.",
        },
    )
    assert scoped_material.status_code == 201, scoped_material.text
    assert scoped_material.json()["question_id"] == first_question_id

    all_materials = client.get(f"/materials?test_id={test['id']}", headers=auth_header(admin_token))
    assert all_materials.status_code == 200
    assert {item["title"] for item in all_materials.json()} == {"General notes", "First question notes"}

    filtered_materials = client.get(
        f"/materials?test_id={test['id']}&question_id={first_question_id}",
        headers=auth_header(admin_token),
    )
    assert filtered_materials.status_code == 200
    assert [item["title"] for item in filtered_materials.json()] == ["First question notes"]

    invalid_material = client.post(
        "/materials",
        headers=auth_header(admin_token),
        json={
            "test_id": test["id"],
            "question_id": "missing-question",
            "title": "Wrong scope",
            "content": "This content should not be accepted because the question is missing.",
        },
    )
    assert invalid_material.status_code == 404
    assert invalid_material.json()["detail"] == "Question not found in this test"

    attempt_response = client.post(
        "/attempts",
        headers=auth_header(admin_token),
        json={"test_id": test["id"]},
    )
    assert attempt_response.status_code == 201, attempt_response.text
    result = client.get(f"/attempts/{attempt_response.json()['id']}/result", headers=auth_header(admin_token))
    assert result.status_code == 200
    assert result.json()["id"] == attempt_response.json()["id"]
    assert [question["id"] for question in result.json()["questions"]] == [first_question_id, second_question_id]


@pytest.mark.asyncio
async def test_text_answer_skips_speechkit_and_completes_processing(client):
    admin_token = register_and_login(client, "admin@example.com")
    test = create_sample_test(client, admin_token)
    material = client.post(
        "/materials",
        headers=auth_header(admin_token),
        json={
            "test_id": test["id"],
            "title": "Text answer material",
            "content": "Transactional outbox stores events in the same database transaction as answer data.",
        },
    )
    assert material.status_code == 201, material.text
    await index_test_materials(test["id"])
    attempt_response = client.post("/attempts", headers=auth_header(admin_token), json={"test_id": test["id"]})
    assert attempt_response.status_code == 201, attempt_response.text
    attempt = attempt_response.json()

    submitted = client.post(
        f"/attempts/{attempt['id']}/questions/{test['questions'][0]['id']}/text",
        headers={**auth_header(admin_token), "Idempotency-Key": "text-answer-1"},
        json={"text": "Transactional outbox saves the answer and event atomically."},
    )

    assert submitted.status_code == 201, submitted.text
    answer = submitted.json()["answers"][0]
    assert answer["answer_type"] == "text"
    assert answer["status"] == "queued_for_transcription"

    replay = client.post(
        f"/attempts/{attempt['id']}/questions/{test['questions'][0]['id']}/text",
        headers={**auth_header(admin_token), "Idempotency-Key": "text-answer-1"},
        json={"text": "Different body should not create another answer."},
    )
    assert replay.status_code == 201
    assert replay.json()["answers"][0]["id"] == answer["id"]

    with SessionLocal() as db:
        outbox = db.scalar(select(OutboxEvent).where(OutboxEvent.event_type == ANSWER_UPLOADED, OutboxEvent.aggregate_id == answer["id"]))
        assert outbox is not None
        processed = await process_answer_uploaded(db, answer_id=answer["id"])
        assert processed.status.value == "completed"

    result = client.get(f"/attempts/{attempt['id']}/result", headers=auth_header(admin_token))
    assert result.status_code == 200
    assert result.json()["answers"][0]["transcript"] == "Transactional outbox saves the answer and event atomically."
    assert result.json()["answers"][0]["review_status"] == "review_recommended"


def test_failed_answer_can_be_retried_with_new_idempotency_key(client):
    admin_token = register_and_login(client, "admin@example.com")
    test = create_sample_test(client, admin_token)
    attempt_response = client.post("/attempts", headers=auth_header(admin_token), json={"test_id": test["id"]})
    assert attempt_response.status_code == 201, attempt_response.text
    attempt = attempt_response.json()

    submitted = client.post(
        f"/attempts/{attempt['id']}/questions/{test['questions'][0]['id']}/text",
        headers={**auth_header(admin_token), "Idempotency-Key": "failed-text-1"},
        json={"text": "First body"},
    )
    assert submitted.status_code == 201, submitted.text
    answer_id = submitted.json()["answers"][0]["id"]

    with SessionLocal() as db:
        answer = db.get(Answer, answer_id)
        assert answer is not None
        answer.status = AnswerStatusEnum.failed
        db.add(answer)
        db.commit()

    retry = client.post(
        f"/attempts/{attempt['id']}/questions/{test['questions'][0]['id']}/text",
        headers={**auth_header(admin_token), "Idempotency-Key": "failed-text-2"},
        json={"text": "Retry body"},
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["answers"][0]["id"] == answer_id
    assert retry.json()["answers"][0]["status"] == "queued_for_transcription"

    with SessionLocal() as db:
        answer = db.get(Answer, answer_id)
        assert answer is not None
        assert answer.idempotency_key == "failed-text-2"
        assert answer.text_response == "Retry body"


@pytest.mark.asyncio
async def test_linked_ai_skill_is_sent_to_answer_evaluation(client):
    admin_token = register_and_login(client, "admin@example.com")
    skill = client.post(
        "/skills",
        headers=auth_header(admin_token),
        json={
            "name": "Terminology focus",
            "description": "Focus on exact terms",
            "content": "Require exact domain terminology and mention missing definitions in feedback.",
        },
    )
    assert skill.status_code == 201, skill.text
    response = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Skill-aware exam",
            "test_type": "self_training",
            "criteria": {"rubric": "Check answer.", "skill_ids": [skill.json()["id"]]},
            "questions": [{"text": "Explain outbox?", "expected_answer": "Atomic event publishing.", "max_score": 10}],
        },
    )
    assert response.status_code == 201, response.text
    test = client.patch(f"/tests/{response.json()['id']}", headers=auth_header(admin_token), json={"status": "published"}).json()
    attempt_response = client.post("/attempts", headers=auth_header(admin_token), json={"test_id": test["id"]})
    answer_response = client.post(
        f"/attempts/{attempt_response.json()['id']}/questions/{test['questions'][0]['id']}/text",
        headers={**auth_header(admin_token), "Idempotency-Key": "skill-text"},
        json={"text": "Outbox stores an event with business data atomically."},
    )
    assert answer_response.status_code == 201, answer_response.text
    ai = RecordingAI()
    with SessionLocal() as db:
        processed = await process_answer_uploaded(db, answer_id=answer_response.json()["answers"][0]["id"], ai=ai)
        assert "Terminology focus" in ai.skill_instructions
        assert "Require exact domain terminology" in ai.skill_instructions
        assert processed.evaluation["ai_skill_instructions_applied"] is True


@pytest.mark.asyncio
async def test_question_weighted_competencies_drive_analytics(client):
    admin_token = register_and_login(client, "admin@example.com")
    response = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Weighted competency exam",
            "test_type": "self_training",
            "questions": [
                {
                    "text": "Explain RAG reliability?",
                    "expected_answer": "Mention retrieval and reliability.",
                    "competencies": [{"name": "RAG", "weight": 3}, {"name": "Reliability", "weight": 1}],
                    "max_score": 12,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    test = client.patch(f"/tests/{response.json()['id']}", headers=auth_header(admin_token), json={"status": "published"}).json()
    attempt_response = client.post("/attempts", headers=auth_header(admin_token), json={"test_id": test["id"]})
    answer_response = client.post(
        f"/attempts/{attempt_response.json()['id']}/questions/{test['questions'][0]['id']}/text",
        headers={**auth_header(admin_token), "Idempotency-Key": "weighted-text"},
        json={"text": "RAG retrieves relevant context and reliability depends on stable processing."},
    )
    assert answer_response.status_code == 201, answer_response.text
    answer_id = answer_response.json()["answers"][0]["id"]
    with SessionLocal() as db:
        processed = await process_answer_uploaded(db, answer_id=answer_id)
        assert processed.evaluation["competency_scores"]["RAG"] == pytest.approx(6.12)
        assert processed.evaluation["competency_scores"]["Reliability"] == pytest.approx(2.04)
        assert processed.evaluation["competency_max_scores"]["RAG"] == pytest.approx(9)
        assert processed.evaluation["competency_max_scores"]["Reliability"] == pytest.approx(3)

    analytics = client.get("/analytics/competencies", headers=auth_header(admin_token))
    assert analytics.status_code == 200
    rows = {item["name"]: item for item in analytics.json()}
    assert rows["RAG"]["score"] == pytest.approx(6.12)
    assert rows["RAG"]["max_score"] == pytest.approx(9)
    assert rows["Reliability"]["score"] == pytest.approx(2.04)
    assert rows["Reliability"]["max_score"] == pytest.approx(3)


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
    assign_test_to_current_user(client, admin_token, first_student, test["id"])

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


def test_methodist_manages_own_learners_and_assignments(client):
    admin_token = register_and_login(client, "admin@example.com")
    methodist_response = client.post(
        "/users",
        headers=auth_header(admin_token),
        json={
            "email": "methodist@example.com",
            "full_name": "Course Methodist",
            "password": "password123",
            "role": "methodist",
        },
    )
    assert methodist_response.status_code == 201, methodist_response.text
    methodist_token = register_and_login(client, "methodist@example.com")
    forbidden_staff_create = client.post(
        "/users",
        headers=auth_header(methodist_token),
        json={
            "email": "teacher-from-methodist@example.com",
            "full_name": "Teacher",
            "password": "password123",
            "role": "teacher",
        },
    )
    assert forbidden_staff_create.status_code == 403

    learner_response = client.post(
        "/users",
        headers=auth_header(methodist_token),
        json={
            "email": "learner@example.com",
            "full_name": "Managed Learner",
            "password": "password123",
            "role": "examinee",
        },
    )
    assert learner_response.status_code == 201, learner_response.text
    assert learner_response.json()["created_by_id"] == methodist_response.json()["id"]

    visible_users = client.get("/users", headers=auth_header(methodist_token))
    assert visible_users.status_code == 200
    assert [item["email"] for item in visible_users.json()] == ["learner@example.com"]

    test = create_sample_test(client, methodist_token)
    assigned = client.post(
        f"/tests/{test['id']}/assign",
        headers=auth_header(methodist_token),
        json={"user_id": learner_response.json()["id"]},
    )
    assert assigned.status_code == 204, assigned.text

    outsider_token = register_and_login(client, "outsider@example.com")
    outsider = client.get("/auth/me", headers=auth_header(outsider_token))
    forbidden_assignment = client.post(
        f"/tests/{test['id']}/assign",
        headers=auth_header(methodist_token),
        json={"user_id": outsider.json()["id"]},
    )
    assert forbidden_assignment.status_code == 403
