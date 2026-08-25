from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import get_current_user
from app.models import Group, GroupMembership, RoleEnum, User
from app.schemas import GroupCreate, GroupMemberAdd, GroupMemberRead, GroupRead
from app.services.moderation import censor_text
from app.services.audit import record_audit


router = APIRouter(prefix="/groups", tags=["groups"])
LEARNER_ROLES = {RoleEnum.student, RoleEnum.examinee, RoleEnum.candidate}
STAFF_ROLES = {RoleEnum.admin, RoleEnum.teacher, RoleEnum.methodist, RoleEnum.interviewer}


@router.get("", response_model=list[GroupRead])
def list_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[GroupRead]:
    _ensure_staff(current_user)
    stmt = select(Group).options(selectinload(Group.memberships).selectinload(GroupMembership.user)).order_by(Group.created_at.desc())
    if current_user.role != RoleEnum.admin:
        stmt = stmt.where(Group.created_by_id == current_user.id)
    return [_serialize_group(group) for group in db.scalars(stmt).all()]


@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroupRead:
    _ensure_staff(current_user)
    group = Group(
        name=censor_text(payload.name),
        description=censor_text(payload.description),
        created_by_id=current_user.id,
    )
    db.add(group)
    db.flush()
    record_audit(db, actor=current_user, action="group.create", entity_type="group", entity_id=group.id, details={"name": group.name})
    db.commit()
    db.refresh(group)
    return _serialize_group(_load_group(db, group.id, current_user))


@router.post("/{group_id}/members", response_model=GroupRead)
def add_group_member(
    group_id: str,
    payload: GroupMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroupRead:
    group = _load_group(db, group_id, current_user)
    target = db.get(User, payload.user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _ensure_can_group_user(current_user, target)
    db.add(GroupMembership(group_id=group.id, user_id=target.id, added_by_id=current_user.id))
    record_audit(db, actor=current_user, action="group.member_add", entity_type="group", entity_id=group.id, details={"user_id": target.id})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already in this group") from None
    return _serialize_group(_load_group(db, group.id, current_user))


@router.delete("/{group_id}/members/{user_id}", response_model=GroupRead)
def remove_group_member(
    group_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroupRead:
    group = _load_group(db, group_id, current_user)
    membership = db.scalar(select(GroupMembership).where(GroupMembership.group_id == group.id, GroupMembership.user_id == user_id))
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group member not found")
    db.delete(membership)
    record_audit(db, actor=current_user, action="group.member_remove", entity_type="group", entity_id=group.id, details={"user_id": user_id})
    db.commit()
    return _serialize_group(_load_group(db, group.id, current_user))


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    group = _load_group(db, group_id, current_user)
    record_audit(db, actor=current_user, action="group.delete", entity_type="group", entity_id=group.id, details={"name": group.name})
    db.delete(group)
    db.commit()


def _load_group(db: Session, group_id: str, current_user: User) -> Group:
    group = db.scalar(
        select(Group)
        .where(Group.id == group_id)
        .options(selectinload(Group.memberships).selectinload(GroupMembership.user))
    )
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if current_user.role != RoleEnum.admin and group.created_by_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return group


def _ensure_staff(user: User) -> None:
    if user.role not in STAFF_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only staff users can manage groups")


def _ensure_can_group_user(current_user: User, target: User) -> None:
    if not target.is_active or target.role not in LEARNER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only active learner accounts can be added to groups")
    if current_user.role != RoleEnum.admin and target.created_by_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff users can add only managed learner accounts")


def _serialize_group(group: Group) -> GroupRead:
    members = sorted((membership.user for membership in group.memberships), key=lambda user: user.full_name.lower())
    return GroupRead(
        id=group.id,
        name=group.name,
        description=group.description,
        created_by_id=group.created_by_id,
        created_at=group.created_at,
        members=[
            GroupMemberRead(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=user.is_active,
            )
            for user in members
        ],
    )
