import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal, init_db
from app.models import Assignment, Material, Question, RoleEnum, Test, TestStatusEnum, TestTypeEnum, User
from app.services.rag import create_material_chunks
from app.services.yandex import YandexAIClient


DEMO_PASSWORD = "password123"
LEGACY_DEMO_EMAILS = {
    "admin@tuneai.local": "admin@tuneai.dev",
    "teacher@tuneai.local": "teacher@tuneai.dev",
    "student@tuneai.local": "student@tuneai.dev",
    "examinee@tuneai.local": "examinee@tuneai.dev",
    "interviewer@tuneai.local": "interviewer@tuneai.dev",
    "candidate@tuneai.local": "candidate@tuneai.dev",
}


async def seed_demo() -> None:
    init_db()
    with SessionLocal() as db:
        normalize_legacy_demo_users(db)

        admin = upsert_user(db, "admin@tuneai.dev", "TuneAI Admin", RoleEnum.admin)
        teacher = upsert_user(db, "teacher@tuneai.dev", "Distributed Systems Teacher", RoleEnum.teacher)
        student = upsert_user(db, "student@tuneai.dev", "Demo Student", RoleEnum.student)
        examinee = upsert_user(db, "examinee@tuneai.dev", "Demo Exam Taker", RoleEnum.examinee)
        interviewer = upsert_user(db, "interviewer@tuneai.dev", "Demo Interviewer", RoleEnum.interviewer)
        candidate = upsert_user(db, "candidate@tuneai.dev", "Demo Candidate", RoleEnum.candidate)

        test = db.scalar(select(Test).where(Test.title == "Распределенные системы"))
        if not test:
            test = Test(
                title="Распределенные системы",
                description="Демо-тест по брокерам сообщений, транзакциям и надежной обработке событий.",
                test_type=TestTypeEnum.self_training,
                status=TestStatusEnum.published,
                criteria={
                    "correctness": "Фактическая корректность терминов и причинно-следственных связей.",
                    "completeness": "Наличие ключевых тезисов: брокер, outbox, идемпотентность, retry/DLQ.",
                    "argumentation": "Ответ объясняет не только что делать, но и зачем это нужно.",
                },
                time_limit_seconds=180,
                owner_id=teacher.id,
            )
            db.add(test)
            db.flush()
        else:
            test.status = TestStatusEnum.published
            test.owner_id = teacher.id

        questions = [
            (
                0,
                "Зачем в распределенной системе нужен брокер сообщений?",
                "Брокер разгружает backend, буферизует задачи, позволяет масштабировать воркеры и переживать сбои внешних API.",
            ),
            (
                1,
                "Как паттерн Transactional Outbox помогает не терять события?",
                "Данные бизнес-операции и событие записываются в одной транзакции БД, а отдельный publisher надежно отправляет событие в брокер.",
            ),
            (
                2,
                "Почему обработчики сообщений должны быть идемпотентными?",
                "При at-least-once delivery сообщение может прийти повторно, поэтому повторная обработка не должна дублировать результат.",
            ),
        ]
        for order_index, text, expected in questions:
            question = db.scalar(select(Question).where(Question.test_id == test.id, Question.order_index == order_index))
            if question:
                question.text = text
                question.expected_answer = expected
                question.max_score = 10
            else:
                db.add(
                    Question(
                        test_id=test.id,
                        order_index=order_index,
                        text=text,
                        expected_answer=expected,
                        max_score=10,
                    )
                )

        assignment = db.scalar(select(Assignment).where(Assignment.test_id == test.id, Assignment.user_id == student.id))
        if not assignment:
            db.add(Assignment(test_id=test.id, user_id=student.id, created_by_id=admin.id))

        material = db.scalar(select(Material).where(Material.test_id == test.id, Material.title == "Конспект: надежная обработка"))
        if not material:
            material = Material(
                test_id=test.id,
                owner_id=teacher.id,
                title="Конспект: надежная обработка",
                content=(
                    "Брокер сообщений используется как буфер между API и воркерами. Он позволяет быстро принять ответ "
                    "пользователя, поставить задачу в очередь и обработать ее асинхронно. Transactional Outbox решает "
                    "проблему атомарности: запись ответа и событие публикации сохраняются в одной транзакции базы данных. "
                    "Outbox publisher затем отправляет pending events в брокер и помечает их published. Так задача не "
                    "теряется, даже если backend упал между сохранением ответа и публикацией сообщения. В большинстве "
                    "брокеров практичная модель доставки — at-least-once, поэтому обработчики должны быть идемпотентными. "
                    "Retry помогает переживать временные ошибки Yandex API, а dead-letter queue сохраняет задачи, которые "
                    "не удалось обработать после нескольких попыток."
                ),
            )
            db.add(material)
            db.flush()
            await create_material_chunks(db, material, YandexAIClient())

        exam = db.scalar(select(Test).where(Test.title == "Экзамен: распределенные системы"))
        if not exam:
            exam = Test(
                title="Экзамен: распределенные системы",
                description="Закрытый экзаменационный сценарий. Его видит только назначенный examinee.",
                test_type=TestTypeEnum.exam,
                status=TestStatusEnum.published,
                criteria={
                    "correctness": "Точность определения брокера, outbox и идемпотентности.",
                    "completeness": "Наличие ключевых тезисов про атомарность, retry и обработку повторов.",
                    "argumentation": "Ответ должен объяснять причинно-следственную связь, а не перечислять термины.",
                },
                time_limit_seconds=300,
                owner_id=teacher.id,
            )
            db.add(exam)
            db.flush()
        else:
            exam.status = TestStatusEnum.published
            exam.owner_id = teacher.id

        exam_questions = [
            (
                0,
                "Объясните, почему запись ответа и outbox-события должна происходить в одной транзакции.",
                "Нужно объяснить атомарность: если ответ сохранен, событие тоже сохранено; при откате нет частичного состояния.",
            ),
            (
                1,
                "Что должен делать worker при повторной доставке сообщения?",
                "Worker должен быть идемпотентным: проверять уже обработанный ответ и не создавать дубликаты результата.",
            ),
        ]
        for order_index, text, expected in exam_questions:
            question = db.scalar(select(Question).where(Question.test_id == exam.id, Question.order_index == order_index))
            if question:
                question.text = text
                question.expected_answer = expected
                question.max_score = 10
            else:
                db.add(
                    Question(
                        test_id=exam.id,
                        order_index=order_index,
                        text=text,
                        expected_answer=expected,
                        max_score=10,
                    )
                )

        exam_assignment = db.scalar(select(Assignment).where(Assignment.test_id == exam.id, Assignment.user_id == examinee.id))
        if not exam_assignment:
            db.add(Assignment(test_id=exam.id, user_id=examinee.id, created_by_id=admin.id))

        interview = db.scalar(select(Test).where(Test.title == "Интервью: backend reliability"))
        if not interview:
            interview = Test(
                title="Интервью: backend reliability",
                description="Демо-сценарий технического интервью с устным разбором архитектурного решения.",
                test_type=TestTypeEnum.interview,
                status=TestStatusEnum.published,
                criteria={
                    "correctness": "Кандидат объясняет очередь, worker, хранение аудио, retry и идемпотентность.",
                    "completeness": "Ответ покрывает API, фоновые задачи, обработку ошибок и наблюдаемость.",
                    "argumentation": "Кандидат связывает техническое решение с пользовательским сценарием и надежностью.",
                    "agent_profile": "interview-coach",
                },
                time_limit_seconds=420,
                owner_id=interviewer.id,
            )
            db.add(interview)
            db.flush()
        else:
            interview.status = TestStatusEnum.published
            interview.owner_id = interviewer.id

        interview_questions = [
            (
                0,
                "Расскажите, как вы бы спроектировали очередь обработки голосовых ответов.",
                "Хороший ответ покрывает API, очередь, worker, ретраи, идемпотентность, хранение аудио и наблюдаемость.",
            ),
            (
                1,
                "Как вы поймете, что AI-проверка начала деградировать в продакшене?",
                "Нужно упомянуть метрики ошибок, долю ручных проверок, confidence, задержки, алерты и аудит примеров.",
            ),
        ]
        for order_index, text, expected in interview_questions:
            question = db.scalar(select(Question).where(Question.test_id == interview.id, Question.order_index == order_index))
            if question:
                question.text = text
                question.expected_answer = expected
                question.max_score = 10
            else:
                db.add(
                    Question(
                        test_id=interview.id,
                        order_index=order_index,
                        text=text,
                        expected_answer=expected,
                        max_score=10,
                    )
                )

        interview_assignment = db.scalar(
            select(Assignment).where(Assignment.test_id == interview.id, Assignment.user_id == candidate.id)
        )
        if not interview_assignment:
            db.add(Assignment(test_id=interview.id, user_id=candidate.id, created_by_id=admin.id))

        db.commit()
        print("Demo data is ready.")
        print(f"Admin:   admin@tuneai.dev / {DEMO_PASSWORD}")
        print(f"Teacher: teacher@tuneai.dev / {DEMO_PASSWORD}")
        print(f"Student/self-training: student@tuneai.dev / {DEMO_PASSWORD}")
        print(f"Exam taker: examinee@tuneai.dev / {DEMO_PASSWORD}")
        print(f"Interviewer: interviewer@tuneai.dev / {DEMO_PASSWORD}")
        print(f"Candidate: candidate@tuneai.dev / {DEMO_PASSWORD}")


def normalize_legacy_demo_users(db) -> None:
    for legacy_email, preferred_email in LEGACY_DEMO_EMAILS.items():
        legacy_user = db.scalar(select(User).where(User.email == legacy_email))
        if not legacy_user:
            continue

        preferred_user = db.scalar(select(User).where(User.email == preferred_email))
        if preferred_user:
            legacy_user.email = f"legacy-{legacy_user.id[:8]}@tuneai.dev"
            legacy_user.is_active = False
        else:
            legacy_user.email = preferred_email
            legacy_user.is_active = True


def upsert_user(db, email: str, full_name: str, role: RoleEnum) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        user.full_name = full_name
        user.role = role
        user.is_active = True
        return user
    user = User(email=email, full_name=full_name, hashed_password=hash_password(DEMO_PASSWORD), role=role)
    db.add(user)
    db.flush()
    return user


if __name__ == "__main__":
    asyncio.run(seed_demo())
