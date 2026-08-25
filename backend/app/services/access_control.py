from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assignment, Attempt, RoleEnum, Test, TestStatusEnum, User


def can_manage_test(test: Test, user: User) -> bool:
    return user.role == RoleEnum.admin or test.owner_id == user.id


def can_view_test(db: Session, test: Test, user: User) -> bool:
    if can_manage_test(test, user):
        return True
    if _has_started_attempt(db, test, user):
        return True
    return test.status == TestStatusEnum.published and _has_assignment(db, test, user)


def can_take_test(db: Session, test: Test, user: User) -> bool:
    if can_manage_test(test, user):
        return True
    return test.status == TestStatusEnum.published and _has_assignment(db, test, user)


def _has_assignment(db: Session, test: Test, user: User) -> bool:
    assignment = db.scalar(select(Assignment.id).where(Assignment.test_id == test.id, Assignment.user_id == user.id))
    return assignment is not None


def _has_started_attempt(db: Session, test: Test, user: User) -> bool:
    attempt = db.scalar(select(Attempt.id).where(Attempt.test_id == test.id, Attempt.user_id == user.id))
    return attempt is not None
