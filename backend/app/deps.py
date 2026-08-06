from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models import RoleEnum, User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        user_id = decode_token(credentials.credentials, "access")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")
    if user.must_change_password and request.url.path not in {"/auth/me", "/auth/change-password"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password change required")
    return user


def require_roles(*roles: RoleEnum) -> Callable[[User], User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency


def _configured_roles(role_names: list[str], fallback: set[RoleEnum]) -> set[RoleEnum]:
    roles: set[RoleEnum] = {RoleEnum.admin}
    for role_name in role_names:
        try:
            roles.add(RoleEnum(role_name.strip()))
        except ValueError:
            continue
    return roles or fallback


def can_create_tests(user: User) -> bool:
    roles = _configured_roles(
        get_settings().test_creator_roles,
        {RoleEnum.student, RoleEnum.methodist, RoleEnum.teacher, RoleEnum.interviewer, RoleEnum.admin},
    )
    return user.role in roles


def can_review_answers(user: User) -> bool:
    roles = _configured_roles(
        get_settings().answer_reviewer_roles,
        {RoleEnum.teacher, RoleEnum.interviewer, RoleEnum.admin},
    )
    return user.role in roles


def is_admin(user: User) -> bool:
    return user.role == RoleEnum.admin
