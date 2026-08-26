from copy import deepcopy

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models import Question, SourceImport, SourceImportStatusEnum, Test, User, new_id
from app.schemas import QuestionRead, SourceImportGenerateRequest, SourceImportRead
from app.services.access_control import can_manage_test
from app.services.audit import record_audit
from app.services.outbox import SOURCE_GENERATION_REQUESTED, add_outbox_event
from app.services.source_imports import extract_source_segments
from app.services.storage import StorageService


router = APIRouter(prefix="/source-imports", tags=["source imports"])
PRESENTATION_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


@router.get("", response_model=list[SourceImportRead])
def list_source_imports(
    test_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SourceImport]:
    test = _managed_test(db, test_id, user)
    return list(db.scalars(select(SourceImport).where(SourceImport.test_id == test.id).order_by(SourceImport.created_at.desc())).all())


@router.post("/upload", response_model=SourceImportRead, status_code=status.HTTP_201_CREATED)
async def upload_source(
    test_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SourceImport:
    test = _managed_test(db, test_id, user)
    filename = file.filename or "presentation"
    normalized_type = (file.content_type or "").split(";", 1)[0].lower()
    if normalized_type not in PRESENTATION_TYPES and not filename.lower().endswith((".pptx", ".pdf")):
        raise HTTPException(status_code=415, detail="Загрузите презентацию PPTX или PDF")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Файл пуст")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Презентация больше 25 МБ")
    source = SourceImport(
        id=new_id(),
        test_id=test.id,
        owner_id=user.id,
        source_filename=filename,
        content_type=normalized_type or "application/octet-stream",
        status=SourceImportStatusEnum.uploaded,
    )
    try:
        source.segments = extract_source_segments(raw, normalized_type, filename)
        source.object_key = StorageService().save_source(source.id, filename, normalized_type, raw)
        source.status = SourceImportStatusEnum.ready
    except Exception as exc:
        source.status = SourceImportStatusEnum.failed
        source.error_message = str(exc)[:4000]
    db.add(source)
    record_audit(db, actor=user, action="source.upload", entity_type="source_import", entity_id=source.id, details={"test_id": test.id, "filename": filename})
    db.commit()
    db.refresh(source)
    return source


@router.get("/{source_id}", response_model=SourceImportRead)
def get_source_import(
    source_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SourceImport:
    return _managed_source(db, source_id, user)


@router.post("/{source_id}/generate", response_model=SourceImportRead, status_code=status.HTTP_202_ACCEPTED)
def generate_from_source(
    source_id: str,
    payload: SourceImportGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SourceImport:
    source = _managed_source(db, source_id, user)
    if source.status not in {SourceImportStatusEnum.ready, SourceImportStatusEnum.completed, SourceImportStatusEnum.failed}:
        raise HTTPException(status_code=409, detail="Источник уже обрабатывается")
    available_ids = {str(item.get("id")) for item in source.segments}
    if not set(payload.excluded_segment_ids).issubset(available_ids):
        raise HTTPException(status_code=422, detail="Неизвестный слайд в списке исключений")
    source.excluded_segment_ids = payload.excluded_segment_ids
    source.generation_config = payload.model_dump(mode="json")
    source.status = SourceImportStatusEnum.queued
    source.error_message = None
    db.add(source)
    add_outbox_event(db, SOURCE_GENERATION_REQUESTED, source.id, {"source_import_id": source.id, "test_id": source.test_id})
    record_audit(db, actor=user, action="source.generate", entity_type="source_import", entity_id=source.id, details={"count": payload.count})
    db.commit()
    db.refresh(source)
    return source


@router.post("/{source_id}/candidates/{candidate_id}/accept", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
def accept_candidate(
    source_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Question:
    source = _managed_source(db, source_id, user, for_update=True)
    candidates = deepcopy(list(source.candidates or []))
    candidate = next((item for item in candidates if item.get("id") == candidate_id), None)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Предложенный вопрос не найден")
    if candidate.get("status") == "accepted":
        question_id = candidate.get("question_id")
        existing = db.get(Question, question_id) if question_id else None
        if existing:
            return existing
    order_index = len(list(db.scalars(select(Question.id).where(Question.test_id == source.test_id)).all()))
    question = Question(
        test_id=source.test_id,
        text=str(candidate.get("text") or ""),
        expected_answer=str(candidate.get("expected_answer") or ""),
        question_type=str(candidate.get("question_type") or "open_response"),
        options=list(candidate.get("options") or []),
        correct_option_ids=list(candidate.get("correct_option_ids") or []),
        explanation=str(candidate.get("explanation") or ""),
        source_refs=list(candidate.get("source_refs") or []),
        competencies=list(candidate.get("competencies") or []),
        answer_mode=str(candidate.get("answer_mode") or "both"),
        order_index=order_index,
        max_score=float(candidate.get("max_score") or 10),
    )
    db.add(question)
    db.flush()
    candidate["status"] = "accepted"
    candidate["question_id"] = question.id
    source.candidates = [dict(item) for item in candidates]
    db.add(source)
    record_audit(db, actor=user, action="question.accept_generated", entity_type="question", entity_id=question.id, details={"source_import_id": source.id})
    db.commit()
    db.refresh(question)
    return question


def _managed_source(db: Session, source_id: str, user: User, *, for_update: bool = False) -> SourceImport:
    statement = select(SourceImport).where(SourceImport.id == source_id)
    if for_update:
        statement = statement.with_for_update()
    source = db.scalar(statement)
    if source is None:
        raise HTTPException(status_code=404, detail="Источник не найден")
    _managed_test(db, source.test_id, user)
    return source


def _managed_test(db: Session, test_id: str, user: User) -> Test:
    test = db.get(Test, test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="Assessment не найден")
    if not can_manage_test(test, user):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return test
