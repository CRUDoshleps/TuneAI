import math
import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Material, MaterialChunk, MaterialIndexStatusEnum
from app.services.ai_provider_runtime import TuneAIClient, get_active_ai_client


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 160) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end])
        if end == len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


async def create_material_chunks(db: Session, material: Material, ai: TuneAIClient | None = None) -> list[MaterialChunk]:
    ai = ai or get_active_ai_client(db)
    for existing in list(db.scalars(select(MaterialChunk).where(MaterialChunk.material_id == material.id)).all()):
        db.delete(existing)
    db.flush()
    chunks: list[MaterialChunk] = []
    for index, chunk in enumerate(chunk_text(material.content)):
        embedding = await ai.embed_document(chunk)
        row = MaterialChunk(
            material_id=material.id,
            organization_id=material.organization_id,
            course_id=material.course_id,
            test_id=material.test_id,
            question_id=material.question_id,
            chunk_index=index,
            text=chunk,
            embedding=embedding,
        )
        db.add(row)
        chunks.append(row)
    material.chunk_count = len(chunks)
    db.add(material)
    return chunks


async def index_material(db: Session, material_id: str, ai: TuneAIClient | None = None) -> Material:
    material = db.get(Material, material_id)
    if material is None:
        raise ValueError(f"Material {material_id} not found")
    try:
        material.index_status = MaterialIndexStatusEnum.parsing
        material.index_error = None
        db.add(material)
        db.commit()
        material.index_status = MaterialIndexStatusEnum.chunking
        db.add(material)
        db.commit()
        material.index_status = MaterialIndexStatusEnum.embedding
        db.add(material)
        db.commit()
        await create_material_chunks(db, material, ai)
        material.index_status = MaterialIndexStatusEnum.indexed
        material.index_error = None
        db.add(material)
        db.commit()
        return material
    except Exception as exc:
        material.index_status = MaterialIndexStatusEnum.failed
        material.index_error = str(exc)[:4000]
        db.add(material)
        db.commit()
        return material


async def retrieve_context(
    db: Session,
    *,
    test_id: str,
    question_id: str | None = None,
    query: str,
    limit: int = 5,
    material_policy: str = "test_and_question",
    ai: TuneAIClient | None = None,
) -> list[str]:
    if material_policy == "none":
        return []
    stmt = _context_query(db, test_id=test_id, question_id=question_id, material_policy=material_policy)
    rows = list(db.scalars(stmt).all())
    if not rows:
        return []
    ai = ai or get_active_ai_client(db)
    query_embedding = await ai.embed_query(query)
    scored = [(_cosine(query_embedding, row.embedding), row.text) for row in rows]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [text for score, text in scored[:limit] if score > -1]


def material_chunks_for_policy(
    db: Session,
    *,
    test_id: str,
    question_id: str | None = None,
    material_policy: str = "test_and_question",
) -> list[MaterialChunk]:
    if material_policy == "none":
        return []
    return list(db.scalars(_context_query(db, test_id=test_id, question_id=question_id, material_policy=material_policy)).all())


def _context_query(db: Session, *, test_id: str, question_id: str | None, material_policy: str):
    from app.models import Test

    test = db.get(Test, test_id)
    criteria = test.criteria if test else {}
    course_id = _criteria_string(criteria, "course_id")
    organization_id = _criteria_string(criteria, "organization_id")
    stmt = select(MaterialChunk).join(Material).where(Material.index_status == MaterialIndexStatusEnum.indexed)
    if material_policy == "question_only":
        return stmt.where(MaterialChunk.test_id == test_id, MaterialChunk.question_id == question_id)
    if material_policy == "course_library":
        linked = [MaterialChunk.test_id == test_id]
        if course_id:
            linked.append(MaterialChunk.course_id == course_id)
        return stmt.where(or_(*linked))
    if material_policy == "organization_library":
        linked = [MaterialChunk.test_id == test_id]
        if organization_id:
            linked.append(MaterialChunk.organization_id == organization_id)
        elif course_id:
            linked.append(MaterialChunk.course_id == course_id)
        return stmt.where(or_(*linked))
    if question_id:
        return stmt.where(
            MaterialChunk.test_id == test_id,
            or_(MaterialChunk.question_id.is_(None), MaterialChunk.question_id == question_id),
        )
    return stmt.where(MaterialChunk.test_id == test_id, MaterialChunk.question_id.is_(None))


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[i] * right[i] for i in range(size))
    left_norm = math.sqrt(sum(left[i] * left[i] for i in range(size)))
    right_norm = math.sqrt(sum(right[i] * right[i] for i in range(size)))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _criteria_string(criteria: dict | None, key: str) -> str | None:
    value = (criteria or {}).get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None
