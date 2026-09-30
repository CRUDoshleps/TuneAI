import json
import secrets
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Material, MaterialIndexStatusEnum, Question, RoleEnum, Test, TestStatusEnum, TestTypeEnum, User
from app.services.outbox import MATERIAL_UPLOADED, add_outbox_event


QUIZZES = {
    "neuromemes": {
        "title": "Нейромемы",
        "description": "Три картинки: посмотрите и назовите мем вслух.",
        "rubric": "Проверять только название мема. За узнаваемое правильное название или его допустимый вариант дать 10 баллов. Принимать детское произношение, небольшие ошибки распознавания речи, русскую и английскую запись. Не требовать историю, объяснение шутки, полное предложение или точное количество повторов. Для 67 принимать «сикс севен», «шесть семь», «шестьдесят семь», «67», «six seven». Для Сахура принимать «тун тун сахур», «тунг тунг тунг сахур», «сахур». Для крокодила принимать «бомбардиро крокодило», «бомбордиро крокодило», «бомбардиро крокадило», «bombardiro crocodilo». Частично узнанное название оценивать частичными баллами. Ноль — только за неверный мем или отсутствие узнавания. Обратная связь — короткая, доброжелательная и понятная ребёнку.",
        "competencies": ["Узнавание нейромема"],
        "questions_file": "neuromeme_questions.json",
    },
    "memes": {
        "title": "Зачёт по мемам",
        "description": "Пять мемов: узнайте героя и расскажите его историю.",
        "rubric": "Оценивать узнавание мема и понимание шутки. Верная фраза, название или узнаваемое описание ситуации — до 5 баллов, объяснение смысла своими словами — до 5 баллов. Короткий ответ, верно передающий мем и его смысл, заслуживает 8–10 баллов, в том числе близкий по смыслу к примеру ответа. Частичное узнавание или частичное понимание оценивать частичными баллами. Не требовать дословной цитаты, точного порядка чисел, полного названия, года, автора или истории появления. Отсутствие этих деталей не снижает оценку. Ноль — только если в ответе нет ни узнавания мема, ни верного понимания смысла.",
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
        if quiz_key == "memes":
            existing.criteria = {**existing.criteria, "rubric": quiz["rubric"]}
            item = quiz["questions"][1]
            question = db.get(Question, str(uuid5(NAMESPACE_URL, "tuneai:memes:2026:1")))
            question.text = item["title"]
            question.expected_answer = item["expected_answer"]
            question.explanation = item["explanation"]
            material = db.query(Material).filter(Material.question_id == question.id, Material.test_id == existing.id).one()
            if material.title != item["name"] or material.content != item["material"]:
                material.title = item["name"]
                material.content = item["material"]
                material.version += 1
                material.chunks.clear()
                material.chunk_count = 0
                material.index_status = MaterialIndexStatusEnum.pending
                material.index_error = None
                add_outbox_event(db, MATERIAL_UPLOADED, material.id, {"material_id": material.id, "test_id": existing.id})
            db.commit()
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
