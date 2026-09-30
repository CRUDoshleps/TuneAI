import json
import secrets
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Material, MaterialIndexStatusEnum, Question, RoleEnum, Test, TestStatusEnum, TestTypeEnum, User
from app.services.outbox import MATERIAL_UPLOADED, add_outbox_event


MEME_TEST_ID = str(uuid5(NAMESPACE_URL, "tuneai:memes:2026"))
MEME_QUESTIONS = json.loads(Path(__file__).with_name("meme_questions.json").read_text(encoding="utf-8"))


def seed_meme_quiz(db: Session) -> Test:
    existing = db.get(Test, MEME_TEST_ID)
    if existing is not None:
        return existing
    owner = User(
        email="memes-owner@tuneai.dev",
        full_name="Мемный зачёт",
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        role=RoleEnum.methodist,
        is_active=False,
    )
    db.add(owner)
    db.flush()
    test = Test(
        id=MEME_TEST_ID,
        title="Зачёт по мемам",
        description="Пять мемов: узнайте героя и расскажите его историю.",
        test_type=TestTypeEnum.exam,
        status=TestStatusEnum.published,
        owner_id=owner.id,
        criteria={
            "rubric": "Оценить узнавание мема и понимание его истории. Название или верное описание героя — 4 балла, происхождение — 3, смысл — 3. Принимать пересказ своими словами и варианты написания. Не требовать дословной цитаты, точного года или имени автора, если смысл передан верно.",
            "strictness": "soft",
            "material_policy": "question_only",
            "competencies": ["Узнавание мема", "История и смысл"],
        },
    )
    db.add(test)
    for order, item in enumerate(MEME_QUESTIONS):
        question = Question(
            id=str(uuid5(NAMESPACE_URL, f"tuneai:memes:2026:{order}")),
            text=item["title"],
            expected_answer=item["dictation"],
            explanation=f'{item["meaning"]}\n\n{item["lore"]}',
            order_index=order,
            max_score=10,
        )
        test.questions.append(question)
        db.flush()
        material = Material(
            test_id=test.id,
            question_id=question.id,
            owner_id=owner.id,
            title=item["name"],
            content=f'{item["dictation"]}\n{item["lore"]}\nИсточник: {item["source"]}',
            index_status=MaterialIndexStatusEnum.pending,
        )
        db.add(material)
        db.flush()
        add_outbox_event(db, MATERIAL_UPLOADED, material.id, {"material_id": material.id, "test_id": test.id})
    db.commit()
    return test
