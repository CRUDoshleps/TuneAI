from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import get_current_user
from app.metrics import ANSWERS_CREATED
from app.models import (
    Answer,
    AnswerStatusEnum,
    Assignment,
    Attempt,
    Question,
    RoleEnum,
    Test,
    TestStatusEnum,
    TestTypeEnum,
    User,
    new_id,
)
from app.schemas import AnswerRead, AttemptQuestionRead, AttemptRead, AttemptStartRequest
from app.services.outbox import ANSWER_UPLOADED, add_outbox_event
from app.services.storage import StorageService


router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.post("", response_model=AttemptRead, status_code=status.HTTP_201_CREATED)
def start_attempt(
    payload: AttemptStartRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptRead:
    test = db.get(Test, payload.test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    _ensure_can_take(db, test, user)
    questions = list(db.scalars(select(Question).where(Question.test_id == test.id)).all())
    if not questions:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Test does not contain questions")
    attempt = Attempt(test_id=test.id, user_id=user.id)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return _serialize_attempt(db, _load_attempt(db, attempt.id), user)


@router.get("/{attempt_id}", response_model=AttemptRead)
def get_attempt(
    attempt_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptRead:
    attempt = _load_attempt(db, attempt_id)
    _ensure_attempt_access(attempt, user)
    return _serialize_attempt(db, attempt, user)


@router.post("/{attempt_id}/questions/{question_id}/audio", response_model=AttemptRead, status_code=status.HTTP_201_CREATED)
async def upload_answer_audio(
    attempt_id: str,
    question_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptRead:
    attempt = _load_attempt(db, attempt_id)
    if attempt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only attempt owner can upload answers")
    question = db.get(Question, question_id)
    if not question or question.test_id != attempt.test_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in this test")
    if not _can_manage_attempt(attempt, user):
        current_question = _current_answerable_question(db, attempt)
        if current_question is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt already has answers for all questions")
        if question.id != current_question.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Question is not revealed yet")
    existing = db.scalar(select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id == question.id))
    if existing and existing.status not in {AnswerStatusEnum.failed}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Question already has an answer")

    content = await file.read()
    answer_id = existing.id if existing else new_id()
    storage = StorageService()
    object_key = storage.save_audio(answer_id, file, content)
    answer = existing or Answer(id=answer_id, attempt_id=attempt.id, question_id=question.id)
    answer.audio_object_key = object_key
    answer.audio_content_type = file.content_type
    answer.status = AnswerStatusEnum.queued_for_transcription
    answer.error_message = None
    db.add(answer)
    add_outbox_event(
        db,
        event_type=ANSWER_UPLOADED,
        aggregate_id=answer.id,
        payload={"answer_id": answer.id, "attempt_id": attempt.id, "question_id": question.id},
    )
    db.commit()
    ANSWERS_CREATED.inc()
    return _serialize_attempt(db, _load_attempt(db, attempt.id), user)


def _load_attempt(db: Session, attempt_id: str) -> Attempt:
    attempt = db.scalar(
        select(Attempt)
        .where(Attempt.id == attempt_id)
        .options(selectinload(Attempt.answers), selectinload(Attempt.test))
    )
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return attempt


def _ensure_can_take(db: Session, test: Test, user: User) -> None:
    if user.role == RoleEnum.admin or test.owner_id == user.id:
        return
    if (
        user.role == RoleEnum.student
        and test.status == TestStatusEnum.published
        and test.test_type == TestTypeEnum.self_training
    ):
        return
    assignment = db.scalar(select(Assignment).where(Assignment.test_id == test.id, Assignment.user_id == user.id))
    if not assignment:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Test is not assigned to this user")


def _can_manage_attempt(attempt: Attempt, user: User) -> bool:
    return user.role == RoleEnum.admin or attempt.test.owner_id == user.id


def _ensure_attempt_access(attempt: Attempt, user: User) -> None:
    if _can_manage_attempt(attempt, user) or attempt.user_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _ordered_questions(db: Session, attempt: Attempt) -> list[Question]:
    return list(
        db.scalars(select(Question).where(Question.test_id == attempt.test_id).order_by(Question.order_index)).all()
    )


def _current_answerable_question(db: Session, attempt: Attempt) -> Question | None:
    answers_by_question = {answer.question_id: answer for answer in attempt.answers}
    for question in _ordered_questions(db, attempt):
        answer = answers_by_question.get(question.id)
        if answer is None or answer.status == AnswerStatusEnum.failed:
            return question
    return None


def _visible_questions(db: Session, attempt: Attempt, user: User) -> list[Question]:
    questions = _ordered_questions(db, attempt)
    if _can_manage_attempt(attempt, user):
        return questions

    answers_by_question = {answer.question_id: answer for answer in attempt.answers}
    visible: list[Question] = []
    for question in questions:
        answer = answers_by_question.get(question.id)
        visible.append(question)
        if answer is None or answer.status == AnswerStatusEnum.failed:
            break
    return visible


def _serialize_attempt(db: Session, attempt: Attempt, user: User) -> AttemptRead:
    answers = sorted(attempt.answers, key=lambda item: item.created_at)
    return AttemptRead(
        id=attempt.id,
        test_id=attempt.test_id,
        user_id=attempt.user_id,
        status=attempt.status,
        total_score=attempt.total_score,
        max_score=attempt.max_score,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        answers=[AnswerRead.model_validate(answer) for answer in answers],
        questions=[
            AttemptQuestionRead(
                id=question.id,
                text=question.text,
                order_index=question.order_index,
                max_score=question.max_score,
            )
            for question in _visible_questions(db, attempt, user)
        ],
    )
