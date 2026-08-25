import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.models import Assignment, RoleEnum, TestStatusEnum as StatusEnum, TestTypeEnum as TypeEnum, User
from app.scripts.seed_demo import normalize_legacy_demo_users, seed_demo


def make_user(email: str, role: RoleEnum) -> User:
    return User(email=email, full_name=email, hashed_password=hash_password("password123"), role=role)


def test_seed_demo_renames_legacy_local_user_to_preferred_email(db_session):
    db_session.add(make_user("admin@tuneai.local", RoleEnum.admin))
    db_session.commit()

    normalize_legacy_demo_users(db_session)
    db_session.commit()

    user = db_session.scalar(select(User).where(User.email == "admin@tuneai.dev"))
    assert user is not None
    assert user.is_active is True


def test_seed_demo_deactivates_duplicate_legacy_local_user(db_session):
    db_session.add(make_user("student@tuneai.dev", RoleEnum.student))
    legacy = make_user("student@tuneai.local", RoleEnum.student)
    db_session.add(legacy)
    db_session.commit()

    normalize_legacy_demo_users(db_session)
    db_session.commit()

    db_session.refresh(legacy)
    assert legacy.email.startswith("legacy-")
    assert legacy.email.endswith("@tuneai.dev")
    assert legacy.is_active is False


def test_seed_demo_creates_interview_scenario_for_candidate(db_session):
    from app.models import Test as TestModel

    asyncio.run(seed_demo())

    candidate = db_session.scalar(select(User).where(User.email == "candidate@tuneai.dev"))
    interviewer = db_session.scalar(select(User).where(User.email == "interviewer@tuneai.dev"))
    interview = db_session.scalar(select(TestModel).where(TestModel.title == "Интервью: backend reliability"))

    assert candidate is not None
    assert candidate.role == RoleEnum.candidate
    assert interviewer is not None
    assert interviewer.role == RoleEnum.interviewer
    assert interview is not None
    assert interview.test_type == TypeEnum.interview
    assert interview.status == StatusEnum.published
    assert interview.owner_id == interviewer.id
    assert db_session.scalar(
        select(Assignment).where(Assignment.test_id == interview.id, Assignment.user_id == candidate.id)
    )
