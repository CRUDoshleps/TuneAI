from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.deps import get_current_user, require_roles
from app.models import Assignment, RoleEnum, Test, User
from app.schemas import UserCreateAdmin, UserCreateStaff, UserRead, UserRoleUpdate


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    if current_user.role == RoleEnum.admin:
        return list(db.scalars(select(User).order_by(User.created_at.desc())).all())
    if current_user.role not in {RoleEnum.teacher, RoleEnum.methodist, RoleEnum.interviewer}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only staff users can list manageable users")
    owned_test_ids = select(Test.id).where(Test.owner_id == current_user.id)
    assigned_user_ids = select(Assignment.user_id).where(Assignment.test_id.in_(owned_test_ids))
    rows = db.scalars(
        select(User)
        .where(
            User.role.in_([RoleEnum.student, RoleEnum.examinee, RoleEnum.candidate]),
            ((User.created_by_id == current_user.id) | (User.id.in_(assigned_user_ids))),
        )
        .order_by(User.created_at.desc())
    )
    return list(rows.all())


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateAdmin | UserCreateStaff,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != RoleEnum.admin:
        if current_user.role not in {RoleEnum.teacher, RoleEnum.methodist, RoleEnum.interviewer}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only staff users can create manageable users")
        if payload.role not in {RoleEnum.student, RoleEnum.examinee, RoleEnum.candidate}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff users can create only learner accounts")
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        created_by_id=None if current_user.role == RoleEnum.admin else current_user.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.admin)),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Admin cannot deactivate own account")
    if user.id == current_user.id and payload.role != RoleEnum.admin:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Admin cannot remove own admin role")
    user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
