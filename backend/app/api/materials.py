from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models import Material, RoleEnum, Test, User
from app.schemas import MaterialCreate, MaterialRead
from app.services.rag import create_material_chunks
from app.services.yandex import YandexAIClient


router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("", response_model=list[MaterialRead])
def list_materials(
    test_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Material]:
    test = db.get(Test, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    _ensure_manager(test, user)
    return list(db.scalars(select(Material).where(Material.test_id == test_id).order_by(Material.created_at.desc())).all())


@router.post("", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Material:
    test = db.get(Test, payload.test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    _ensure_manager(test, user)
    material = Material(test_id=test.id, owner_id=user.id, title=payload.title, content=payload.content)
    db.add(material)
    db.flush()
    await create_material_chunks(db, material, YandexAIClient())
    db.commit()
    db.refresh(material)
    return material


@router.post("/upload", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
async def upload_material(
    test_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Material:
    if file.content_type not in {"text/plain", "text/markdown", "application/octet-stream"}:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only text material is supported")
    content = (await file.read()).decode("utf-8", errors="replace")
    payload = MaterialCreate(test_id=test_id, title=file.filename or "Uploaded material", content=content)
    material = await create_material(payload, db, user)
    material.source_filename = file.filename
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def _ensure_manager(test: Test, user: User) -> None:
    if user.role == RoleEnum.admin or test.owner_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner or admin can manage materials")

