from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import (
    Answer,
    Assignment,
    Attempt,
    AuditLog,
    GeneratedQuestionCache,
    Material,
    MaterialChunk,
    MoodleSubmission,
    Question,
    SourceImport,
    Test,
    User,
)


def demo_expiration(ttl_hours: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=ttl_hours)


def cleanup_expired_demo_data(db: Session, now: datetime | None = None) -> int:
    current_time = now or datetime.now(timezone.utc)
    expired_test_ids = list(
        db.scalars(select(Test.id).where(Test.is_demo.is_(True), Test.expires_at.is_not(None), Test.expires_at <= current_time)).all()
    )
    expired_user_ids = list(
        db.scalars(select(User.id).where(User.is_demo.is_(True), User.expires_at.is_not(None), User.expires_at <= current_time)).all()
    )
    if not expired_test_ids and not expired_user_ids:
        return 0

    question_ids = list(db.scalars(select(Question.id).where(Question.test_id.in_(expired_test_ids))).all())
    attempt_ids = list(
        db.scalars(select(Attempt.id).where(or_(Attempt.test_id.in_(expired_test_ids), Attempt.user_id.in_(expired_user_ids)))).all()
    )
    answer_ids = list(
        db.scalars(select(Answer.id).where(or_(Answer.attempt_id.in_(attempt_ids), Answer.question_id.in_(question_ids)))).all()
    )
    material_ids = list(
        db.scalars(
            select(Material.id).where(
                or_(
                    Material.test_id.in_(expired_test_ids),
                    Material.question_id.in_(question_ids),
                    Material.owner_id.in_(expired_user_ids),
                )
            )
        ).all()
    )
    if expired_test_ids or expired_user_ids or attempt_ids or question_ids or answer_ids:
        db.execute(
            delete(MoodleSubmission).where(
                or_(
                    MoodleSubmission.test_id.in_(expired_test_ids),
                    MoodleSubmission.user_id.in_(expired_user_ids),
                    MoodleSubmission.attempt_id.in_(attempt_ids),
                    MoodleSubmission.question_id.in_(question_ids),
                    MoodleSubmission.answer_id.in_(answer_ids),
                )
            )
        )
    if material_ids or expired_test_ids or question_ids:
        db.execute(
            delete(MaterialChunk).where(
                or_(
                    MaterialChunk.material_id.in_(material_ids),
                    MaterialChunk.test_id.in_(expired_test_ids),
                    MaterialChunk.question_id.in_(question_ids),
                )
            )
        )
    if answer_ids:
        db.execute(delete(Answer).where(Answer.id.in_(answer_ids)))
    if attempt_ids:
        db.execute(delete(Attempt).where(Attempt.id.in_(attempt_ids)))
    if material_ids:
        db.execute(delete(Material).where(Material.id.in_(material_ids)))
    if expired_test_ids:
        db.execute(delete(Assignment).where(Assignment.test_id.in_(expired_test_ids)))
        db.execute(delete(SourceImport).where(SourceImport.test_id.in_(expired_test_ids)))
        db.execute(delete(GeneratedQuestionCache).where(GeneratedQuestionCache.test_id.in_(expired_test_ids)))
        db.execute(delete(Question).where(Question.id.in_(question_ids)))
        db.execute(delete(Test).where(Test.id.in_(expired_test_ids)))
    if expired_user_ids:
        db.execute(update(AuditLog).where(AuditLog.actor_id.in_(expired_user_ids)).values(actor_id=None))
        db.execute(
            delete(Assignment).where(
                or_(Assignment.user_id.in_(expired_user_ids), Assignment.created_by_id.in_(expired_user_ids))
            )
        )
        db.execute(delete(User).where(User.id.in_(expired_user_ids)))
    db.commit()
    return len(expired_test_ids) + len(expired_user_ids)


def recent_demo_user_count(db: Session, window_hours: int = 1) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    return db.scalar(select(func.count(User.id)).where(User.is_demo.is_(True), User.created_at >= since)) or 0
