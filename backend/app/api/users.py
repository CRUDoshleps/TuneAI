import hashlib
import csv
import io
import secrets
import string
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.deps import get_current_user, require_roles
from app.models import Assignment, RoleEnum, Test, User, UserInvite, utcnow
from app.schemas import PasswordResetRead, UserBatchCreate, UserCreateAdmin, UserCreateStaff, UserInviteCreate, UserInviteRead, UserProvisionRead, UserRead, UserRoleUpdate


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
        must_change_password=False,
        created_by_id=None if current_user.role == RoleEnum.admin else current_user.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/batch", response_model=list[UserProvisionRead], status_code=status.HTTP_201_CREATED)
def create_users_batch(
    payload: UserBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserProvisionRead]:
    if current_user.role not in {RoleEnum.admin, RoleEnum.teacher, RoleEnum.methodist, RoleEnum.interviewer}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only staff users can provision learner accounts")
    emails = [item.email.lower() for item in payload.users]
    if len(emails) != len(set(emails)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="User list contains duplicate emails")
    existing = set(db.scalars(select(User.email).where(User.email.in_(emails))).all())
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Emails are already registered: {', '.join(sorted(existing))}")

    created: list[tuple[User, str]] = []
    for item in payload.users:
        if item.role not in {RoleEnum.student, RoleEnum.examinee, RoleEnum.candidate}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Batch provisioning is limited to learner accounts")
        password = item.password or _generate_temporary_password()
        generated_password = item.password is None
        user = User(
            email=item.email.lower(),
            full_name=item.full_name,
            hashed_password=hash_password(password),
            role=item.role,
            must_change_password=generated_password,
            created_by_id=None if current_user.role == RoleEnum.admin else current_user.id,
        )
        db.add(user)
        created.append((user, password))
    db.commit()
    for user, _ in created:
        db.refresh(user)
    return [UserProvisionRead(user=UserRead.model_validate(user), password=password) for user, password in created]


@router.post("/batch/csv", response_model=list[UserProvisionRead], status_code=status.HTTP_201_CREATED)
async def create_users_batch_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserProvisionRead]:
    content = (await file.read()).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(content)))
    if not rows:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="CSV file is empty")
    users = []
    for row in rows:
        users.append(
            {
                "email": (row.get("email") or "").strip(),
                "full_name": (row.get("full_name") or row.get("name") or "").strip(),
                "role": (row.get("role") or "examinee").strip(),
                "password": (row.get("password") or "").strip() or None,
            }
        )
    return create_users_batch(UserBatchCreate(users=users), db, current_user)


@router.post("/invites", response_model=UserInviteRead, status_code=status.HTTP_201_CREATED)
def create_invite(
    payload: UserInviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserInviteRead:
    if current_user.role not in {RoleEnum.admin, RoleEnum.teacher, RoleEnum.methodist, RoleEnum.interviewer}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only staff users can invite learners")
    if current_user.role != RoleEnum.admin and payload.role not in {RoleEnum.student, RoleEnum.examinee, RoleEnum.candidate}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff users can invite only learner accounts")
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
    token = secrets.token_urlsafe(32)
    invite = UserInvite(
        email=payload.email.lower(),
        full_name=payload.full_name,
        role=payload.role,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        created_by_id=current_user.id,
        expires_at=utcnow() + timedelta(days=payload.expires_in_days),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return _serialize_invite(invite, token)


@router.post("/{user_id}/reset-password", response_model=PasswordResetRead)
def reset_user_password(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PasswordResetRead:
    if current_user.role not in {RoleEnum.admin, RoleEnum.teacher, RoleEnum.methodist, RoleEnum.interviewer}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only staff users can reset learner passwords")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_user.role != RoleEnum.admin:
        if user.role not in {RoleEnum.student, RoleEnum.examinee, RoleEnum.candidate} or user.created_by_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff users can reset only their learner accounts")
    password = _generate_temporary_password()
    user.hashed_password = hash_password(password)
    user.must_change_password = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return PasswordResetRead(user=UserRead.model_validate(user), temporary_password=password)


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


def _generate_temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(item.islower() for item in password) and any(item.isupper() for item in password) and any(item.isdigit() for item in password):
            return password


def _serialize_invite(invite: UserInvite, token: str) -> UserInviteRead:
    return UserInviteRead(
        id=invite.id,
        email=invite.email,
        full_name=invite.full_name,
        role=invite.role,
        invite_url=f"/accept-invite?token={token}",
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at,
    )
