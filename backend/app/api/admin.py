from datetime import datetime, timezone
import csv
import io
from pathlib import Path
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import get_db
from app.deps import require_roles
from app.models import Answer, AnswerStatusEnum, Attempt, AttemptStatusEnum, AuditLog, OutboxEvent, OutboxStatusEnum, RoleEnum, Test, User
from app.schemas import AdminAttemptRead, AdminDashboard, AdminFailedJobRead, AuditLogRead, SystemHealthCheck, SystemHealthRead
from app.services.ai_provider_runtime import active_provider_readiness
from app.services.audit import record_audit
from app.services.outbox import ANSWER_UPLOADED, add_outbox_event


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_model=AdminDashboard)
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> AdminDashboard:
    completed_attempts = db.scalar(select(func.count(Attempt.id)).where(Attempt.status == AttemptStatusEnum.completed)) or 0
    average_percent = db.scalar(
        select(func.avg(Attempt.total_score * 100.0 / Attempt.max_score)).where(
            Attempt.status == AttemptStatusEnum.completed,
            Attempt.max_score.is_not(None),
            Attempt.max_score > 0,
        )
    ) or 0
    review_pending = db.scalar(
        select(func.count(Answer.id)).where(
            Answer.status == AnswerStatusEnum.completed,
            Answer.reviewed_at.is_(None),
        )
    ) or 0
    return AdminDashboard(
        users=db.scalar(select(func.count(User.id))) or 0,
        tests=db.scalar(select(func.count(Test.id))) or 0,
        attempts=db.scalar(select(func.count(Attempt.id))) or 0,
        answers_completed=db.scalar(select(func.count(Answer.id)).where(Answer.status == AnswerStatusEnum.completed)) or 0,
        answers_failed=db.scalar(select(func.count(Answer.id)).where(Answer.status == AnswerStatusEnum.failed)) or 0,
        outbox_pending=db.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.status == OutboxStatusEnum.pending)) or 0,
        attempts_completed=completed_attempts,
        average_score_percent=round(float(average_percent), 1),
        review_pending=review_pending,
    )


@router.get("/system", response_model=SystemHealthRead)
def system_health(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> SystemHealthRead:
    settings = get_settings()
    checks: list[SystemHealthCheck] = []
    checks.append(_check("backend", "ok", "API отвечает и авторизация работает"))
    try:
        db.execute(select(1))
        checks.append(_check("database", "ok", "PostgreSQL доступен"))
    except Exception as exc:
        checks.append(_check("database", "error", str(exc)))
    pending = db.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.status == OutboxStatusEnum.pending)) or 0
    failed = db.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.status == OutboxStatusEnum.failed)) or 0
    if failed:
        checks.append(_check("worker", "error", f"Failed outbox events: {failed}"))
    elif pending:
        checks.append(_check("worker", "warning", f"Pending outbox events: {pending}"))
    else:
        checks.append(_check("worker", "ok", "Outbox queue is empty"))
    checks.append(_rabbitmq_check(settings.rabbitmq_url))
    checks.append(_storage_check(settings.upload_dir))
    ai = active_provider_readiness(db, settings)
    if ai:
        checks.append(_check("ai", "ok" if ai.configured else "warning", f"{ai.provider}: {ai.status}"))
    else:
        configured = settings.yandex_mock or bool((settings.yandex_api_key or settings.yandex_iam_token) and settings.yandex_folder_id)
        checks.append(_check("ai", "ok" if configured else "warning", "Mock AI" if settings.yandex_mock else "AI credentials are incomplete"))
    moodle_ready = settings.moodle_integration_enabled and bool(settings.moodle_integration_token)
    checks.append(_check("moodle", "ok" if moodle_ready else "warning", "Moodle service API enabled" if moodle_ready else "Moodle service API is disabled"))
    last_answer_error = db.scalar(select(Answer.error_message).where(Answer.status == AnswerStatusEnum.failed).order_by(Answer.updated_at.desc()).limit(1))
    last_outbox_error = db.scalar(select(OutboxEvent.last_error).where(OutboxEvent.status == OutboxStatusEnum.failed).order_by(OutboxEvent.created_at.desc()).limit(1))
    last_error = last_answer_error or last_outbox_error
    checks.append(_check("last_error", "warning" if last_error else "ok", last_error or "Ошибок обработки не найдено"))
    return SystemHealthRead(checks=checks, generated_at=datetime.now(timezone.utc))


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


@router.post("/failed-jobs/{job_id}/retry", response_model=AdminFailedJobRead)
def retry_failed_job(
    job_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(RoleEnum.admin)),
) -> AdminFailedJobRead:
    answer = db.get(Answer, job_id)
    if answer is not None:
        if answer.status != AnswerStatusEnum.failed:
            raise HTTPException(status_code=409, detail="Ответ уже не находится в состоянии ошибки")
        pending = db.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == answer.id,
                OutboxEvent.event_type == ANSWER_UPLOADED,
                OutboxEvent.status == OutboxStatusEnum.pending,
            )
        )
        if pending is None:
            add_outbox_event(db, ANSWER_UPLOADED, answer.id, {"answer_id": answer.id, "attempt_id": answer.attempt_id, "question_id": answer.question_id})
        answer.status = AnswerStatusEnum.queued_for_transcription
        answer.error_message = None
        db.add(answer)
        record_audit(db, actor=admin, action="job.retry", entity_type="answer", entity_id=answer.id)
        db.commit()
        return AdminFailedJobRead(id=answer.id, kind="answer", status="pending", aggregate_id=answer.id, error_message="Повторный запуск поставлен в очередь", created_at=answer.updated_at)

    event = db.get(OutboxEvent, job_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if event.status == OutboxStatusEnum.failed:
        event.status = OutboxStatusEnum.pending
        event.attempts = 0
        event.last_error = None
        event.published_at = None
        db.add(event)
    record_audit(db, actor=admin, action="job.retry", entity_type="outbox_event", entity_id=event.id)
    db.commit()
    return AdminFailedJobRead(id=event.id, kind="outbox", status="pending", aggregate_id=event.aggregate_id, error_message="Повторный запуск поставлен в очередь", created_at=event.created_at)


@router.get("/audit-log", response_model=list[AuditLogRead])
def audit_log(
    action: str | None = None,
    entity_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> list[AuditLogRead]:
    stmt = select(AuditLog, User.email).outerjoin(User, AuditLog.actor_id == User.id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    rows = db.execute(stmt.order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [
        AuditLogRead(
            id=item.id,
            actor_id=item.actor_id,
            actor_email=email,
            action=item.action,
            entity_type=item.entity_type,
            entity_id=item.entity_id,
            details=item.details or {},
            created_at=item.created_at,
        )
        for item, email in rows
    ]


@router.get("/results/export.csv")
def export_results_csv(
    test_id: str | None = None,
    user_id: str | None = None,
    attempt_status: AttemptStatusEnum | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> StreamingResponse:
    stmt = select(Attempt).options(selectinload(Attempt.test), selectinload(Attempt.user), selectinload(Attempt.answers)).order_by(Attempt.started_at.desc())
    if test_id:
        stmt = stmt.where(Attempt.test_id == test_id)
    if user_id:
        stmt = stmt.where(Attempt.user_id == user_id)
    if attempt_status:
        stmt = stmt.where(Attempt.status == attempt_status)
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["attempt_id", "user_email", "test", "status", "score", "max_score", "answers", "started_at", "completed_at"])
    for attempt in db.scalars(stmt.limit(10000)).all():
        writer.writerow([
            attempt.id,
            attempt.user.email,
            attempt.test.title,
            attempt.status.value,
            attempt.total_score if attempt.total_score is not None else "",
            attempt.max_score if attempt.max_score is not None else "",
            len(attempt.answers),
            attempt.started_at.isoformat(),
            attempt.completed_at.isoformat() if attempt.completed_at else "",
        ])
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tuneai-results.csv"'},
    )


def _check(name: str, status: str, detail: str) -> SystemHealthCheck:
    return SystemHealthCheck(name=name, status=status, detail=detail)


def _rabbitmq_check(url: str) -> SystemHealthCheck:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5672
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return _check("rabbitmq", "ok", f"{host}:{port} доступен")
    except OSError as exc:
        return _check("rabbitmq", "warning", f"{host}:{port} недоступен: {exc}")


def _storage_check(upload_dir: str) -> SystemHealthCheck:
    try:
        path = Path(upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".tuneai-health"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return _check("storage", "ok", f"{path} доступен для записи")
    except OSError as exc:
        return _check("storage", "error", str(exc))
