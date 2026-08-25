import hashlib
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.deps import get_current_user
from app.models import RoleEnum, User, UserInvite, utcnow
from app.schemas import AcceptInviteRequest, ChangePasswordRequest, LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserRead
from app.services.audit import record_audit


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=RoleEnum.student,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/admin/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_admin(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
    admin_count = db.scalar(select(func.count(User.id)).where(User.role == RoleEnum.admin)) or 0
    if admin_count:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin registration is closed")
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=RoleEnum.admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user.role == RoleEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use admin login")
    record_audit(db, actor=user, action="auth.login", entity_type="user", entity_id=user.id)
    db.commit()
    return TokenPair(access_token=create_token(user.id, "access"), refresh_token=create_token(user.id, "refresh"))


@router.post("/admin/login", response_model=TokenPair)
def admin_login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin account required")
    record_audit(db, actor=user, action="auth.admin_login", entity_type="user", entity_id=user.id)
    db.commit()
    return TokenPair(access_token=create_token(user.id, "access"), refresh_token=create_token(user.id, "refresh"))


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user_id = decode_token(payload.refresh_token, "refresh")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")
    return TokenPair(access_token=create_token(user.id, "access"), refresh_token=create_token(user.id, "refresh"))


@router.post("/change-password", response_model=UserRead)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")
    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/invites/accept", response_model=TokenPair)
def accept_invite(payload: AcceptInviteRequest, db: Session = Depends(get_db)) -> TokenPair:
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    invite = db.scalar(select(UserInvite).where(UserInvite.token_hash == token_hash))
    if not invite or invite.accepted_at is not None or _as_aware(invite.expires_at) < utcnow():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found or expired")
    existing = db.scalar(select(User).where(User.email == invite.email.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
    user = User(
        email=invite.email.lower(),
        full_name=invite.full_name,
        hashed_password=hash_password(payload.password),
        role=invite.role,
        created_by_id=invite.created_by_id,
    )
    invite.accepted_at = utcnow()
    db.add(user)
    db.add(invite)
    db.commit()
    db.refresh(user)
    return TokenPair(access_token=create_token(user.id, "access"), refresh_token=create_token(user.id, "refresh"))


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user


def _as_aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
