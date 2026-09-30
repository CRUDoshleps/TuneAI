import io
import wave
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models import Answer, Attempt, Material, OutboxEvent, Question, Test as DbTest, User
from app.services.demo_cleanup import cleanup_expired_demo_data
from app.services.meme_quiz import MEME_TEST_ID, seed_meme_quiz
from app.services.outbox import ANSWER_UPLOADED, MATERIAL_UPLOADED
from app.services.processing import process_answer_uploaded
from app.services.rag import index_material
from app.tests.conftest import auth_header


def test_meme_seed_preserves_five_prepared_questions_on_repeat(client):
    with SessionLocal() as db:
        test = seed_meme_quiz(db)
        ids = [question.id for question in test.questions]
        seed_meme_quiz(db)
        assert [question.id for question in test.questions] == ids
        assert db.query(Question).filter(Question.test_id == MEME_TEST_ID).count() == 5
        answers = [q.expected_answer for q in sorted(test.questions, key=lambda q: q.order_index)]
        for expected, fragment in zip(answers, ["черемша", "Пиббл", "пухососы", "Вернера Херцога", "стриме Коляки"]):
            assert fragment in expected
        assert db.query(Material).filter(Material.test_id == MEME_TEST_ID).count() == 5
        assert db.query(OutboxEvent).filter(OutboxEvent.event_type == MATERIAL_UPLOADED).count() == 5
        assert test.expires_at is None and not test.is_demo
    catalog = client.get("/public/memes")
    assert catalog.status_code == 200
    assert len(catalog.json()["questions"]) == 5
    assert "expected_answer" not in catalog.text
    assert "explanation" not in catalog.text


@pytest.mark.asyncio
async def test_meme_voice_and_text_answers_reach_real_processing_and_unlock_lore(client):
    with SessionLocal() as db:
        seed_meme_quiz(db)
        for material in db.query(Material).filter(Material.test_id == MEME_TEST_ID).all():
            await index_material(db, material.id)
    catalog = client.get("/public/memes").json()
    response = client.post("/public/memes/start")
    assert response.status_code == 201, response.text
    session = response.json()
    headers = auth_header(session["tokens"]["access_token"])
    attempt_id = session["attempt"]["id"]
    assert len(session["attempt"]["questions"]) == 1
    assert "expected_answer" not in response.text
    for index, question in enumerate(catalog["questions"]):
        base = f"/attempts/{attempt_id}/questions/{question['id']}"
        explanation = f"/public/memes/attempts/{attempt_id}/questions/{question['id']}/explanation"
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
    result = client.get(f"/attempts/{attempt_id}", headers=headers).json()
    assert result["status"] == "completed"
    assert len(result["answers"]) == 5
    assert result["max_score"] == 50
    assert result["total_score"] == sum(answer["score"] for answer in result["answers"])


def test_meme_guests_cannot_read_each_others_attempts_or_change_reference_answers(client):
    with SessionLocal() as db:
        seed_meme_quiz(db)
    first = client.post("/public/memes/start").json()
    second = client.post("/public/memes/start").json()
    headers = auth_header(second["tokens"]["access_token"])
    attempt_id = first["attempt"]["id"]
    question_id = first["attempt"]["questions"][0]["id"]
    assert first["attempt"]["user_id"] != second["attempt"]["user_id"]
    assert client.get(f"/attempts/{attempt_id}", headers=headers).status_code == 403
    assert client.get(f"/public/memes/attempts/{attempt_id}/questions/{question_id}/explanation", headers=headers).status_code == 404
    assert client.patch(f"/tests/{MEME_TEST_ID}/questions/{question_id}", headers=headers, json={"expected_answer": "Wrong reference"}).status_code == 403
    tests = client.get("/tests", headers=headers).json()
    assert len(tests) == 1 and tests[0]["questions"] == []
    assert client.post(f"/attempts/{second['attempt']['id']}/questions/{question_id}/text", headers=headers, json={"text": "Черемша"}).status_code == 201


def test_meme_guest_cleanup_keeps_prepared_quiz_and_materials(client):
    with SessionLocal() as db:
        seed_meme_quiz(db)
    session = client.post("/public/memes/start").json()
    with SessionLocal() as db:
        user = db.get(User, session["attempt"]["user_id"])
        user.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        assert cleanup_expired_demo_data(db) == 1
        assert db.get(User, session["attempt"]["user_id"]) is None
        assert db.get(Attempt, session["attempt"]["id"]) is None
        assert db.query(Answer).count() == 0
        assert db.get(DbTest, MEME_TEST_ID) is not None
        assert db.query(Question).filter(Question.test_id == MEME_TEST_ID).count() == 5
        assert db.query(Material).filter(Material.test_id == MEME_TEST_ID).count() == 5


def test_meme_quiz_reports_unseeded_disabled_and_capacity_states(client, monkeypatch):
    from app.core.config import get_settings

    assert client.get("/public/memes").status_code == 503
    assert client.post("/public/memes/start").status_code == 503
    with SessionLocal() as db:
        seed_meme_quiz(db)
    get_settings.cache_clear()
    monkeypatch.setenv("DEMO_BOOTSTRAP_LIMIT_PER_HOUR", "0")
    try:
        assert client.post("/public/memes/start").status_code == 429
        monkeypatch.setenv("DEMO_BOOTSTRAP_ENABLED", "false")
        get_settings.cache_clear()
        assert client.get("/public/memes").status_code == 404
        assert client.post("/public/memes/start").status_code == 404
    finally:
        get_settings.cache_clear()
