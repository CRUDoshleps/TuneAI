import io
import wave
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models import Answer, Attempt, Material, MaterialChunk, MaterialIndexStatusEnum, OutboxEvent, Question, Test as DbTest, User
from app.services.demo_cleanup import cleanup_expired_demo_data
from app.services.conference_quiz import QUIZZES, seed_conference_quiz
from app.services.outbox import ANSWER_UPLOADED, MATERIAL_UPLOADED
from app.services.processing import process_answer_uploaded
from app.services.rag import index_material, retrieve_context
from app.tests.conftest import auth_header


@pytest.fixture(params=["memes", "education", "neuromemes"])
def quiz_key(request):
    return request.param


@pytest.fixture
def quiz_id(quiz_key):
    return QUIZZES[quiz_key]["id"]


@pytest.fixture
def question_count(quiz_key):
    return 3 if quiz_key == "neuromemes" else 5


def test_conference_seed_preserves_prepared_questions_on_repeat(client, quiz_key, quiz_id, question_count):
    with SessionLocal() as db:
        test = seed_conference_quiz(db, quiz_key)
        ids = [question.id for question in test.questions]
        seed_conference_quiz(db, quiz_key)
        assert [question.id for question in test.questions] == ids
        assert db.query(Question).filter(Question.test_id == quiz_id).count() == question_count
        answers = [q.expected_answer for q in sorted(test.questions, key=lambda q: q.order_index)]
        fragments = {
            "memes": ["черемша", "Минут 10–15", "пухососы", "Вернера Херцога", "стриме Коляки"],
            "education": ["рынок труда", "Запоминание", "фундаментальность", "советский период", "Минпросвещения"],
            "neuromemes": ["Сикс севен", "Тун Тун Сахур", "Бомбардиро Крокодило"],
        }
        for expected, fragment in zip(answers, fragments[quiz_key]):
            assert fragment in expected
        assert db.query(Material).filter(Material.test_id == quiz_id).count() == question_count
        assert db.query(OutboxEvent).filter(OutboxEvent.event_type == MATERIAL_UPLOADED).count() == question_count
        assert test.expires_at is None and not test.is_demo
    catalog = client.get(f"/public/{quiz_key}")
    assert catalog.status_code == 200
    assert len(catalog.json()["questions"]) == question_count
    assert "expected_answer" not in catalog.text
    assert "explanation" not in catalog.text


@pytest.mark.asyncio
async def test_meme_replacement_updates_existing_reference_and_removes_old_rag_context(client):
    with SessionLocal() as db:
        test = seed_conference_quiz(db, "memes")
        question = sorted(test.questions, key=lambda q: q.order_index)[1]
        question_id = question.id
        question.expected_answer = "Это Пиббл — белый пёс на сёрфе."
        question.explanation = "Беззаботный пёс из нейросетевых видео."
        test.criteria = {**test.criteria, "rubric": "Обязательно назвать автора и год."}
        material = db.query(Material).filter(Material.question_id == question.id).one()
        material.title = "Пиббл"
        material.content = question.expected_answer
        db.commit()
        await index_material(db, material.id)
        assert db.query(MaterialChunk).filter(MaterialChunk.material_id == material.id).count() > 0

        seed_conference_quiz(db, "memes")
        assert question.id == question_id
        assert "путается в числах" in question.expected_answer
        assert "Пиббл" not in question.explanation
        assert "8–10 баллов" in test.criteria["rubric"]
        assert material.index_status == MaterialIndexStatusEnum.pending
        assert material.version == 2
        assert material.chunk_count == 0
        assert db.query(MaterialChunk).filter(MaterialChunk.material_id == material.id).count() == 0
        assert db.query(OutboxEvent).filter(OutboxEvent.event_type == MATERIAL_UPLOADED).count() == 6
        seed_conference_quiz(db, "memes")
        assert material.version == 2
        assert db.query(OutboxEvent).filter(OutboxEvent.event_type == MATERIAL_UPLOADED).count() == 6

        await index_material(db, material.id)
        context = await retrieve_context(db, test_id=test.id, question_id=question.id, query="путается во времени", material_policy="question_only")
        assert context and all("Пиббл" not in chunk for chunk in context)
        assert any("путается в числах" in chunk for chunk in context)
    question = client.get("/public/memes").json()["questions"][1]
    assert question["id"] == question_id
    assert question["image"] == "/memes/minutes.jpg"


@pytest.mark.asyncio
async def test_conference_voice_and_text_answers_reach_real_processing_and_unlock_lore(client, quiz_key, quiz_id, question_count):
    with SessionLocal() as db:
        seed_conference_quiz(db, quiz_key)
        for material in db.query(Material).filter(Material.test_id == quiz_id).all():
            await index_material(db, material.id)
    catalog = client.get(f"/public/{quiz_key}").json()
    response = client.post(f"/public/{quiz_key}/start")
    assert response.status_code == 201, response.text
    session = response.json()
    headers = auth_header(session["tokens"]["access_token"])
    attempt_id = session["attempt"]["id"]
    assert len(session["attempt"]["questions"]) == 1
    assert "expected_answer" not in response.text
    for index, question in enumerate(catalog["questions"]):
        base = f"/attempts/{attempt_id}/questions/{question['id']}"
        explanation = f"/public/{quiz_key}/attempts/{attempt_id}/questions/{question['id']}/explanation"
        assert client.get(explanation, headers=headers).status_code == 409
        if index == 0:
            audio = io.BytesIO()
            with wave.open(audio, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"\x00\x00" * 16000)
            submitted = client.post(base + "/audio", headers=headers, files={"file": ("answer.wav", audio.getvalue(), "audio/wav")})
        else:
            submitted = client.post(base + "/text", headers=headers, json={"text": "Это мем из интернета, у которого есть своя история."})
        assert submitted.status_code == 201, submitted.text
        answer_id = submitted.json()["answers"][-1]["id"]
        with SessionLocal() as db:
            assert db.query(OutboxEvent).filter(OutboxEvent.aggregate_id == answer_id, OutboxEvent.event_type == ANSWER_UPLOADED).count() == 1
            processed = await process_answer_uploaded(db, answer_id=answer_id)
            assert processed.status.value == "completed", processed.error_message
            assert processed.transcript
            assert processed.evaluation["grounded"] is True
        revealed = client.get(explanation, headers=headers)
        assert revealed.status_code == 200
        assert revealed.json()["expected_answer"]
        assert revealed.json()["explanation"]
        other_quiz = "education" if quiz_key == "memes" else "memes"
        assert client.get(f"/public/{other_quiz}/attempts/{attempt_id}/questions/{question['id']}/explanation", headers=headers).status_code == 404
    result = client.get(f"/attempts/{attempt_id}", headers=headers).json()
    assert result["status"] == "completed"
    assert len(result["answers"]) == question_count
    assert result["max_score"] == question_count * 10
    assert result["total_score"] == sum(answer["score"] for answer in result["answers"])


def test_conference_guests_cannot_read_each_others_attempts_or_change_reference_answers(client, quiz_key, quiz_id):
    with SessionLocal() as db:
        seed_conference_quiz(db, quiz_key)
    first = client.post(f"/public/{quiz_key}/start").json()
    second = client.post(f"/public/{quiz_key}/start").json()
    headers = auth_header(second["tokens"]["access_token"])
    attempt_id = first["attempt"]["id"]
    question_id = first["attempt"]["questions"][0]["id"]
    assert first["attempt"]["user_id"] != second["attempt"]["user_id"]
    assert client.get(f"/attempts/{attempt_id}", headers=headers).status_code == 403
    assert client.get(f"/public/{quiz_key}/attempts/{attempt_id}/questions/{question_id}/explanation", headers=headers).status_code == 404
    assert client.patch(f"/tests/{quiz_id}/questions/{question_id}", headers=headers, json={"expected_answer": "Wrong reference"}).status_code == 403
    tests = client.get("/tests", headers=headers).json()
    assert len(tests) == 1 and tests[0]["questions"] == []
    assert client.post(f"/attempts/{second['attempt']['id']}/questions/{question_id}/text", headers=headers, json={"text": "Черемша"}).status_code == 201


def test_conference_guest_cleanup_keeps_prepared_quiz_and_materials(client, quiz_key, quiz_id, question_count):
    with SessionLocal() as db:
        seed_conference_quiz(db, quiz_key)
    session = client.post(f"/public/{quiz_key}/start").json()
    with SessionLocal() as db:
        user = db.get(User, session["attempt"]["user_id"])
        user.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        assert cleanup_expired_demo_data(db) == 1
        assert db.get(User, session["attempt"]["user_id"]) is None
        assert db.get(Attempt, session["attempt"]["id"]) is None
        assert db.query(Answer).count() == 0
        assert db.get(DbTest, quiz_id) is not None
        assert db.query(Question).filter(Question.test_id == quiz_id).count() == question_count
        assert db.query(Material).filter(Material.test_id == quiz_id).count() == question_count


def test_conference_quiz_reports_unseeded_disabled_and_capacity_states(client, monkeypatch, quiz_key, quiz_id):
    from app.core.config import get_settings

    assert client.get(f"/public/{quiz_key}").status_code == 503
    assert client.post(f"/public/{quiz_key}/start").status_code == 503
    with SessionLocal() as db:
        seed_conference_quiz(db, quiz_key)
    get_settings.cache_clear()
    monkeypatch.setenv("DEMO_BOOTSTRAP_LIMIT_PER_HOUR", "0")
    try:
        assert client.post(f"/public/{quiz_key}/start").status_code == 429
        monkeypatch.setenv("DEMO_BOOTSTRAP_ENABLED", "false")
        get_settings.cache_clear()
        assert client.get(f"/public/{quiz_key}").status_code == 404
        assert client.post(f"/public/{quiz_key}/start").status_code == 404
    finally:
        get_settings.cache_clear()


def test_education_seed_preserves_existing_meme_answers_and_separates_materials(client):
    with SessionLocal() as db:
        memes = seed_conference_quiz(db, "memes")
        original_id = memes.questions[0].id
        memes.questions[0].expected_answer = "Существующий эталон."
        db.commit()
        education = seed_conference_quiz(db, "education")
        seed_conference_quiz(db, "memes")
        assert memes.questions[0].id == original_id
        assert memes.questions[0].expected_answer == "Существующий эталон."
        assert education.id != memes.id
        assert {q.id for q in memes.questions}.isdisjoint({q.id for q in education.questions})
        assert db.query(Question).count() == 10
        assert db.query(Material).count() == 10
        for question in education.questions:
            material = db.query(Material).filter(Material.question_id == question.id).one()
            assert material.test_id == education.id
            assert f"Раздел {question.order_index + 1}." in material.content
            assert "Черемша" not in material.content
    assert all(q["image"] is None for q in client.get("/public/education").json()["questions"])
    assert all(q["image"] for q in client.get("/public/memes").json()["questions"])
