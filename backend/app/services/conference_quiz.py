import json
import secrets
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Material, MaterialIndexStatusEnum, Question, RoleEnum, Test, TestStatusEnum, TestTypeEnum, User
from app.services.outbox import MATERIAL_UPLOADED, add_outbox_event


QUIZZES = {
    "memes": {
        "title": "Зачёт по мемам",
        "description": "Пять мемов: узнайте героя и расскажите его историю.",
        "rubric": "Оценить узнавание мема и понимание его истории. Название или верное описание героя — 4 балла, происхождение — 3, смысл — 3. Принимать пересказ своими словами и варианты написания. Не требовать дословной цитаты, точного года или имени автора, если смысл передан верно.",
        "competencies": ["Узнавание мема", "История и смысл"],
        "questions_file": "meme_questions.json",
    },
    "education": {
        "title": "Образование и ИИ",
        "description": "Пять вопросов об образовании, мышлении и ответственности по материалу YaC/e 2026.",
        "rubric": "Оценить ответ по соответствующему разделу предоставленного материала: основные идеи — 4 балла, объяснение связей и причин — 4, ясность и самостоятельность формулировки — 2. Принимать пересказ своими словами. Не требовать дословного текста, дополнительных исторических дат, имён или сведений вне материала. Не требовать пример, если вопрос его не просит. Не снижать оценку за отсутствие термина, если смысл верно передан.",
        "competencies": ["Понимание образования и ИИ", "Аргументация"],
        "questions_file": "education_questions.json",
    },
}
for quiz_key, quiz in QUIZZES.items():
    quiz["id"] = str(uuid5(NAMESPACE_URL, f"tuneai:{quiz_key}:2026"))
    quiz["questions"] = json.loads(Path(__file__).with_name(quiz["questions_file"]).read_text(encoding="utf-8"))


def seed_conference_quiz(db: Session, quiz_key: str) -> Test:
    quiz = QUIZZES[quiz_key]
    existing = db.get(Test, quiz["id"])
    if existing is not None:
        return existing
    owner = User(
        email=f"{quiz_key}-owner@tuneai.dev",
        full_name=quiz["title"],
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        role=RoleEnum.methodist,
        is_active=False,
    )
    db.add(owner)
    db.flush()
    test = Test(
        id=quiz["id"],
        title=quiz["title"],
        description=quiz["description"],
        test_type=TestTypeEnum.exam,
        status=TestStatusEnum.published,
        owner_id=owner.id,
        criteria={
            "rubric": quiz["rubric"],
            "strictness": "soft",
            "material_policy": "question_only",
            "competencies": quiz["competencies"],
        },
    )
    db.add(test)
    for order, item in enumerate(quiz["questions"]):
        question = Question(
            id=str(uuid5(NAMESPACE_URL, f"tuneai:{quiz_key}:2026:{order}")),
            text=item["title"],
            expected_answer=item["expected_answer"],
            explanation=item["explanation"],
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
            content=item["material"],
            index_status=MaterialIndexStatusEnum.pending,
        )
        db.add(material)
        db.flush()
        add_outbox_event(db, MATERIAL_UPLOADED, material.id, {"material_id": material.id, "test_id": test.id})
    db.commit()
    return test
