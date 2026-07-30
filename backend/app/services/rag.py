import math
import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Material, MaterialChunk
from app.services.yandex import YandexAIClient


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


async def create_material_chunks(db: Session, material: Material, ai: YandexAIClient | None = None) -> list[MaterialChunk]:
    ai = ai or YandexAIClient()
    chunks: list[MaterialChunk] = []
    for index, chunk in enumerate(chunk_text(material.content)):
        embedding = await ai.embed_document(chunk)
        row = MaterialChunk(
            material_id=material.id,
            test_id=material.test_id,
            question_id=material.question_id,
            chunk_index=index,
            text=chunk,
            embedding=embedding,
        )
        db.add(row)
        chunks.append(row)
    return chunks


async def retrieve_context(
    db: Session,
    *,
    test_id: str,
    question_id: str | None = None,
    query: str,
    limit: int = 5,
    ai: YandexAIClient | None = None,
) -> list[str]:
    stmt = select(MaterialChunk).where(MaterialChunk.test_id == test_id)
    if question_id:
        stmt = stmt.where(or_(MaterialChunk.question_id.is_(None), MaterialChunk.question_id == question_id))
    else:
        stmt = stmt.where(MaterialChunk.question_id.is_(None))
    rows = list(db.scalars(stmt).all())
    if not rows:
        return []
    ai = ai or YandexAIClient()
    query_embedding = await ai.embed_query(query)
    scored = [(_cosine(query_embedding, row.embedding), row.text) for row in rows]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [text for score, text in scored[:limit] if score > -1]


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
