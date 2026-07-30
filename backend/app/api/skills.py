from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import can_create_tests, get_current_user
from app.models import AISkill, RoleEnum, User
from app.schemas import AISkillCreate, AISkillRead, AISkillUpdate
from app.services.moderation import censor_text


router = APIRouter(prefix="/skills", tags=["skills"])

MAX_SKILL_FILE_BYTES = 512 * 1024


@router.get("", response_model=list[AISkillRead])
def list_skills(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AISkill]:
    _ensure_skill_creator(user)
    stmt = select(AISkill).order_by(AISkill.updated_at.desc())
    if user.role != RoleEnum.admin:
        stmt = stmt.where(AISkill.owner_id == user.id)
    return list(db.scalars(stmt).all())


@router.post("", response_model=AISkillRead, status_code=status.HTTP_201_CREATED)
def create_skill(
    payload: AISkillCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AISkill:
    _ensure_skill_creator(user)
    skill = AISkill(
        name=censor_text(payload.name),
        description=censor_text(payload.description),
        content=_normalize_skill_content(payload.content),
        owner_id=user.id,
        is_active=payload.is_active,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@router.post("/upload", response_model=AISkillRead, status_code=status.HTTP_201_CREATED)
async def upload_skill(
    name: str | None = None,
    description: str = "",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AISkill:
    _ensure_skill_creator(user)
    normalized_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    filename = file.filename or "skill.txt"
    if normalized_type not in {"text/plain", "text/markdown", "application/octet-stream"} and not filename.lower().endswith((".txt", ".md")):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only text skill files are supported")
    content = await file.read()
    if len(content) > MAX_SKILL_FILE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Skill file is too large")
    text = content.decode("utf-8", errors="replace")
    skill = AISkill(
        name=censor_text((name or filename).strip()),
        description=censor_text(description),
        content=_normalize_skill_content(text),
        source_filename=filename,
        owner_id=user.id,
        is_active=True,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@router.patch("/{skill_id}", response_model=AISkillRead)
def update_skill(
    skill_id: str,
    payload: AISkillUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AISkill:
    skill = _load_skill(db, skill_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field in {"name", "description"} and value is not None:
            value = censor_text(value)
        elif field == "content" and value is not None:
            value = _normalize_skill_content(value)
        setattr(skill, field, value)
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    skill = _load_skill(db, skill_id, user)
    db.delete(skill)
    db.commit()


def _load_skill(db: Session, skill_id: str, user: User) -> AISkill:
    skill = db.get(AISkill, skill_id)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI skill not found")
    if user.role != RoleEnum.admin and skill.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner or admin can manage this AI skill")
    return skill


def _ensure_skill_creator(user: User) -> None:
    if can_create_tests(user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only test creators can manage AI skills")


def _normalize_skill_content(content: str) -> str:
    text = content.strip()
    if len(text) < 20:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="AI skill content is too short")
    return censor_text(text[:50000])
