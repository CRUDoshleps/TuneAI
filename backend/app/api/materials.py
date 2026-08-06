from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models import Material, MaterialIndexStatusEnum, MaterialScopeEnum, Question, RoleEnum, Test, User
from app.schemas import MaterialCreate, MaterialRead
from app.services.outbox import MATERIAL_UPLOADED, add_outbox_event


router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("", response_model=list[MaterialRead])
def list_materials(
    test_id: str | None = None,
    question_id: str | None = None,
    course_id: str | None = None,
    organization_id: str | None = None,
    scope: MaterialScopeEnum | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Material]:
    query = select(Material)
    if test_id:
        test = db.get(Test, test_id)
        if not test:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
        _ensure_manager(test, user)
        linked_filters = [Material.test_id == test_id]
        course_id_from_test = _criteria_string(test.criteria, "course_id")
        organization_id_from_test = _criteria_string(test.criteria, "organization_id")
        if course_id_from_test:
            linked_filters.append(Material.course_id == course_id_from_test)
        if organization_id_from_test:
            linked_filters.append(Material.organization_id == organization_id_from_test)
        query = query.where(or_(*linked_filters))
    else:
        _ensure_library_manager(user)
        if user.role != RoleEnum.admin:
            query = query.where(Material.owner_id == user.id)
    if question_id:
        query = query.where(Material.question_id == question_id)
    if course_id:
        query = query.where(Material.course_id == course_id)
    if organization_id:
        query = query.where(Material.organization_id == organization_id)
    if scope:
        query = query.where(Material.scope == scope)
    return list(db.scalars(query.order_by(Material.created_at.desc())).all())


@router.post("", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Material:
    test = _load_optional_test(db, payload.test_id, user)
    if payload.question_id:
        question = db.get(Question, payload.question_id)
        if not question or question.test_id != payload.test_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in this test")
    if not test:
        _ensure_library_manager(user)
    material = Material(
        organization_id=(payload.organization_id or _criteria_string(test.criteria, "organization_id")) if test else payload.organization_id,
        course_id=(payload.course_id or _criteria_string(test.criteria, "course_id")) if test else payload.course_id,
        test_id=test.id if test else None,
        question_id=payload.question_id,
        owner_id=user.id,
        title=payload.title,
        content_type=payload.content_type,
        scope=payload.scope,
        version=payload.version,
        content=payload.content,
        index_status=MaterialIndexStatusEnum.uploaded,
    )
    db.add(material)
    db.flush()
    add_outbox_event(db, MATERIAL_UPLOADED, material.id, {"material_id": material.id, "test_id": material.test_id})
    db.commit()
    db.refresh(material)
    return material


@router.post("/upload", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
async def upload_material(
    test_id: str | None = None,
    question_id: str | None = None,
    organization_id: str | None = None,
    course_id: str | None = None,
    scope: MaterialScopeEnum = Query(default=MaterialScopeEnum.test),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Material:
    normalized_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    filename = file.filename or "material.txt"
    if not _is_supported_material_file(normalized_type, filename):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only text PDF DOCX or Markdown material is supported")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Material file is too large")
    content = _extract_text(raw, normalized_type, filename)
    payload = MaterialCreate(
        test_id=test_id,
        question_id=question_id,
        organization_id=organization_id,
        course_id=course_id,
        scope=scope,
        title=file.filename or "Uploaded material",
        content=content,
        content_type=normalized_type or "application/octet-stream",
    )
    material = await create_material(payload, db, user)
    material.source_filename = file.filename
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    material_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    test = db.get(Test, material.test_id)
    if test:
        _ensure_manager(test, user)
    else:
        _ensure_library_manager(user)
        if user.role != RoleEnum.admin and material.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner or admin can manage materials")
    if material.test_id and not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    db.delete(material)
    db.commit()


def _load_optional_test(db: Session, test_id: str | None, user: User) -> Test | None:
    if not test_id:
        return None
    test = db.get(Test, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    _ensure_manager(test, user)
    return test


def _ensure_manager(test: Test, user: User) -> None:
    if user.role == RoleEnum.admin or test.owner_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner or admin can manage materials")


def _ensure_library_manager(user: User) -> None:
    if user.role in {RoleEnum.admin, RoleEnum.teacher, RoleEnum.methodist, RoleEnum.interviewer}:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only test creators can manage material library")


def _criteria_string(criteria: dict | None, key: str) -> str | None:
    value = (criteria or {}).get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _is_supported_material_file(content_type: str, filename: str) -> bool:
    lower = filename.lower()
    return (
        content_type in {
            "text/plain",
            "text/markdown",
            "application/octet-stream",
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        or lower.endswith((".txt", ".md", ".pdf", ".docx"))
    )


def _extract_text(raw: bytes, content_type: str, filename: str) -> str:
    lower = filename.lower()
    if content_type == "application/pdf" or lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="PDF parser is not installed") from exc
        import io

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or lower.endswith(".docx"):
        try:
            from docx import Document
        except ImportError as exc:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="DOCX parser is not installed") from exc
        import io

        document = Document(io.BytesIO(raw))
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    return raw.decode("utf-8", errors="replace")
