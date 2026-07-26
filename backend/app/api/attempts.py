from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import get_current_user, require_roles
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
from app.schemas import (
    AnswerRead,
    AnswerReviewRequest,
    AttemptQuestionRead,
    AttemptRead,
    AttemptStartRequest,
    ReviewQueueItem,
)
from app.services.processing import _refresh_attempt_totals
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


@router.get("", response_model=list[AttemptRead])
def list_my_attempts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AttemptRead]:
    attempts = list(
        db.scalars(
            select(Attempt)
            .where(Attempt.user_id == user.id)
            .options(selectinload(Attempt.answers), selectinload(Attempt.test))
            .order_by(Attempt.started_at.desc())
            .limit(20)
        ).all()
    )
    return [_serialize_attempt(db, attempt, user) for attempt in attempts]


@router.get("/review-queue", response_model=list[ReviewQueueItem])
def review_queue(
    db: Session = Depends(get_db),
    reviewer: User = Depends(require_roles(RoleEnum.admin, RoleEnum.teacher, RoleEnum.interviewer)),
) -> list[ReviewQueueItem]:
    answers = list(
        db.scalars(
            select(Answer)
            .where(Answer.status == AnswerStatusEnum.completed, Answer.reviewed_at.is_(None))
            .options(
                selectinload(Answer.question),
                selectinload(Answer.attempt).selectinload(Attempt.user),
                selectinload(Answer.attempt).selectinload(Attempt.test),
            )
            .order_by(Answer.created_at.desc())
            .limit(200)
        ).all()
    )
    rows: list[ReviewQueueItem] = []
    for answer in answers:
        if reviewer.role != RoleEnum.admin and answer.attempt.test.owner_id != reviewer.id:
            continue
        evaluation = answer.evaluation or {}
        if not evaluation.get("review_recommended"):
            continue
        rows.append(
            ReviewQueueItem(
                answer_id=answer.id,
                attempt_id=answer.attempt_id,
                test_title=answer.attempt.test.title,
                question_text=answer.question.text,
                student_email=answer.attempt.user.email,
                transcript=answer.transcript or "",
                ai_score=answer.score or 0,
                max_score=answer.max_score or answer.question.max_score,
                confidence=float(evaluation.get("confidence") or 0),
                ai_feedback=str(evaluation.get("feedback") or ""),
                source_excerpts=list(evaluation.get("source_excerpts") or [])[:3],
                created_at=answer.created_at,
            )
        )
    return rows[:100]


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


@router.patch("/{attempt_id}/answers/{answer_id}/review", response_model=AnswerRead)
def review_answer(
    attempt_id: str,
    answer_id: str,
    payload: AnswerReviewRequest,
    db: Session = Depends(get_db),
    reviewer: User = Depends(require_roles(RoleEnum.admin, RoleEnum.teacher, RoleEnum.interviewer)),
) -> AnswerRead:
    answer = db.scalar(
        select(Answer)
        .where(Answer.id == answer_id, Answer.attempt_id == attempt_id)
        .options(selectinload(Answer.attempt).selectinload(Attempt.test))
    )
    if not answer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
    if reviewer.role != RoleEnum.admin and answer.attempt.test.owner_id != reviewer.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only test owner or admin can review answers")
    if answer.status != AnswerStatusEnum.completed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only completed answers can be reviewed")
    maximum = answer.max_score or answer.question.max_score
    if payload.score > maximum:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Review score exceeds maximum")

    answer.review_score = payload.score
    answer.review_feedback = payload.feedback.strip()
    answer.reviewed_by_id = reviewer.id
    answer.reviewed_at = datetime.now(timezone.utc)
    db.add(answer)
    db.commit()
    db.refresh(answer)
    _refresh_attempt_totals(db, answer.attempt)
    db.commit()
    return AnswerRead.model_validate(answer)


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
