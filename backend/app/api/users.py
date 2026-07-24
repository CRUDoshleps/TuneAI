from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.deps import require_roles
from app.models import RoleEnum, User
from app.schemas import UserCreateAdmin, UserRead, UserRoleUpdate


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateAdmin,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> User:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
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
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

