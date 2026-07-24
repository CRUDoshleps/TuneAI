from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import require_roles
from app.models import Answer, AnswerStatusEnum, Attempt, OutboxEvent, OutboxStatusEnum, RoleEnum, Test, User
from app.schemas import AdminAttemptRead, AdminDashboard, AdminFailedJobRead


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_model=AdminDashboard)
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> AdminDashboard:
    return AdminDashboard(
        users=db.scalar(select(func.count(User.id))) or 0,
        tests=db.scalar(select(func.count(Test.id))) or 0,
        attempts=db.scalar(select(func.count(Attempt.id))) or 0,
        answers_completed=db.scalar(select(func.count(Answer.id)).where(Answer.status == AnswerStatusEnum.completed)) or 0,
        answers_failed=db.scalar(select(func.count(Answer.id)).where(Answer.status == AnswerStatusEnum.failed)) or 0,
        outbox_pending=db.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.status == OutboxStatusEnum.pending)) or 0,
    )


@router.get("/attempts", response_model=list[AdminAttemptRead])
def list_attempts(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> list[AdminAttemptRead]:
    attempts = list(
        db.scalars(
            select(Attempt)
            .options(selectinload(Attempt.answers), selectinload(Attempt.test), selectinload(Attempt.user))
            .order_by(Attempt.started_at.desc())
            .limit(100)
        ).all()
    )
    rows: list[AdminAttemptRead] = []
    for attempt in attempts:
        answers_total = len(attempt.answers)
        rows.append(
            AdminAttemptRead(
                id=attempt.id,
                test_id=attempt.test_id,
                test_title=attempt.test.title,
                user_id=attempt.user_id,
                user_email=attempt.user.email,
                status=attempt.status,
                total_score=attempt.total_score,
                max_score=attempt.max_score,
                answers_total=answers_total,
                answers_completed=sum(1 for answer in attempt.answers if answer.status == AnswerStatusEnum.completed),
                answers_failed=sum(1 for answer in attempt.answers if answer.status == AnswerStatusEnum.failed),
                started_at=attempt.started_at,
                completed_at=attempt.completed_at,
            )
        )
    return rows


@router.get("/failed-jobs", response_model=list[AdminFailedJobRead])
def list_failed_jobs(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> list[AdminFailedJobRead]:
    rows: list[AdminFailedJobRead] = []
    failed_answers = list(
        db.scalars(
            select(Answer)
            .where(Answer.status == AnswerStatusEnum.failed)
            .options(
                selectinload(Answer.attempt).selectinload(Attempt.user),
                selectinload(Answer.attempt).selectinload(Attempt.test),
            )
            .order_by(Answer.updated_at.desc())
            .limit(50)
        ).all()
    )
    for answer in failed_answers:
        rows.append(
            AdminFailedJobRead(
                id=answer.id,
                kind="answer",
                status=answer.status.value,
                aggregate_id=answer.id,
                user_email=answer.attempt.user.email,
                test_title=answer.attempt.test.title,
                error_message=answer.error_message or "Unknown answer processing error",
                created_at=answer.updated_at,
            )
        )

    failed_outbox = list(
        db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxStatusEnum.failed)
            .order_by(OutboxEvent.created_at.desc())
            .limit(50)
        ).all()
    )
    for event in failed_outbox:
        rows.append(
            AdminFailedJobRead(
                id=event.id,
                kind="outbox",
                status=event.status.value,
                aggregate_id=event.aggregate_id,
                error_message=event.last_error or "Outbox publish failed",
                created_at=event.created_at,
            )
        )
    rows.sort(key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return rows[:100]
