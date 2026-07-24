from sqlalchemy import select

from app.core.security import hash_password
from app.models import RoleEnum, User
from app.scripts.seed_demo import normalize_legacy_demo_users


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
