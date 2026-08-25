from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OutboxEvent, OutboxStatusEnum


ANSWER_UPLOADED = "answer.uploaded"
MATERIAL_UPLOADED = "material.uploaded"
SOURCE_GENERATION_REQUESTED = "source.generation_requested"


def add_outbox_event(db: Session, event_type: str, aggregate_id: str, payload: dict[str, Any]) -> OutboxEvent:
    event = OutboxEvent(event_type=event_type, aggregate_id=aggregate_id, payload=payload)
    db.add(event)
    return event


def get_pending_events(db: Session, limit: int = 100) -> list[OutboxEvent]:
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.status == OutboxStatusEnum.pending)
        .order_by(OutboxEvent.created_at)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def mark_published(db: Session, event: OutboxEvent) -> None:
    event.status = OutboxStatusEnum.published
    event.published_at = datetime.now(timezone.utc)
    db.add(event)


def mark_failed(db: Session, event: OutboxEvent, error: str, max_attempts: int = 5) -> None:
    event.attempts += 1
    event.status = OutboxStatusEnum.failed if event.attempts >= max_attempts else OutboxStatusEnum.pending
    event.last_error = error[:4000]
    db.add(event)
