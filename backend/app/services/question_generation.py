import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GeneratedQuestionCache, MaterialChunk, Question, Test
from app.schemas import GeneratedQuestionCandidate, QuestionCompetency, QuestionGenerationRead, QuestionGenerationRequest
from app.services.rag import material_chunks_for_policy


@dataclass(frozen=True)
class ChunkScore:
    chunk: MaterialChunk
    relevance: float


def generate_questions_from_rag(
    db: Session,
    *,
    test: Test,
    payload: QuestionGenerationRequest,
    created_by_id: str,
) -> QuestionGenerationRead:
    chunks = material_chunks_for_policy(
        db,
        test_id=test.id,
        question_id=payload.question_id,
        material_policy=payload.material_policy,
    )
    ranked = _select_diverse_chunks(chunks, payload.max_context_chunks, payload.max_tokens_budget)
    fingerprint = _fingerprint(test.id, payload, ranked)
    if payload.reuse_existing:
        cached = db.scalar(
            select(GeneratedQuestionCache).where(
                GeneratedQuestionCache.test_id == test.id,
                GeneratedQuestionCache.fingerprint == fingerprint,
            )
        )
        if cached:
            cached_questions = [{**item, "reused": True} for item in cached.questions]
            return QuestionGenerationRead(
                questions=[GeneratedQuestionCandidate(**item) for item in cached_questions],
                reused_count=len(cached.questions),
                source_chunk_count=len(cached.source_chunk_ids),
                token_budget_estimate=cached.token_budget_estimate,
                fingerprint=cached.fingerprint,
            )

    competencies = _test_competencies(test)
    existing_questions = list(db.scalars(select(Question).where(Question.test_id == test.id)).all())
    questions: list[GeneratedQuestionCandidate] = []
    for scored in ranked:
        if len(questions) >= payload.count:
            break
        candidate = _candidate_from_chunk(scored.chunk.text, competencies, scored.relevance)
        reused = _similar_existing(candidate.text, existing_questions)
        if reused:
            questions.append(
                GeneratedQuestionCandidate(
                    text=reused.text,
                    expected_answer=reused.expected_answer,
                    competencies=[QuestionCompetency(**item) for item in reused.competencies],
                    answer_mode=reused.answer_mode,
                    max_score=reused.max_score,
                    source_excerpt=candidate.source_excerpt,
                    novelty_score=0,
                    reused=True,
                )
            )
        else:
            questions.append(candidate)

    cache = GeneratedQuestionCache(
        test_id=test.id,
        fingerprint=fingerprint,
        policy=payload.material_policy,
        requested_count=payload.count,
        source_chunk_ids=[item.chunk.id for item in ranked],
        questions=[item.model_dump(mode="json") for item in questions],
        token_budget_estimate=_token_budget(ranked),
        reused_count=0,
        created_by_id=created_by_id,
    )
    db.add(cache)
    db.commit()
    return QuestionGenerationRead(
        questions=questions,
        reused_count=sum(1 for item in questions if item.reused),
        source_chunk_count=len(ranked),
        token_budget_estimate=cache.token_budget_estimate,
        fingerprint=fingerprint,
    )


def _select_diverse_chunks(chunks: list[MaterialChunk], limit: int, token_budget: int) -> list[ChunkScore]:
    scored = [ChunkScore(chunk=chunk, relevance=_chunk_quality(chunk.text)) for chunk in chunks]
    scored.sort(key=lambda item: item.relevance, reverse=True)
    selected: list[ChunkScore] = []
    spent = 0
    while scored and len(selected) < limit:
        best_index = 0
        best_score = float("-inf")
        for index, item in enumerate(scored[: min(30, len(scored))]):
            novelty_penalty = max((_cosine(item.chunk.embedding, chosen.chunk.embedding) for chosen in selected), default=0)
            mmr = 0.72 * item.relevance - 0.28 * novelty_penalty
            if mmr > best_score:
                best_index = index
                best_score = mmr
        picked = scored.pop(best_index)
        next_cost = _estimate_tokens(picked.chunk.text)
        if selected and spent + next_cost > token_budget:
            break
        selected.append(picked)
        spent += next_cost
    return selected


def _candidate_from_chunk(text: str, competencies: list[QuestionCompetency], novelty: float) -> GeneratedQuestionCandidate:
    sentence = _best_sentence(text)
    phrase = sentence.rstrip(".!?")
    if len(phrase) > 180:
        phrase = phrase[:177].rsplit(" ", 1)[0] + "..."
    return GeneratedQuestionCandidate(
        text=f"Объясните своими словами: {phrase}?",
        expected_answer=sentence,
        competencies=competencies,
        max_score=10,
        source_excerpt=text[:600],
        novelty_score=round(novelty, 4),
    )


def _best_sentence(text: str) -> str:
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if len(item.strip()) >= 40]
    if not sentences:
        return text.strip()[:240]
    return max(sentences, key=_chunk_quality)[:500]


def _chunk_quality(text: str) -> float:
    words = _words(text)
    if not words:
        return 0
    unique = len(set(words))
    domain_terms = sum(1 for word in words if len(word) >= 8)
    return unique / max(len(words), 1) + min(domain_terms / 18, 1)


def _similar_existing(text: str, questions: list[Question]) -> Question | None:
    words = set(_words(text))
    if not words:
        return None
    for question in questions:
        existing = set(_words(question.text))
        if not existing:
            continue
        jaccard = len(words & existing) / len(words | existing)
        if jaccard >= 0.58:
            return question
    return None


def _test_competencies(test: Test) -> list[QuestionCompetency]:
    raw = (test.criteria or {}).get("competencies")
    if isinstance(raw, list) and raw:
        return [QuestionCompetency(name=str(item), weight=1) for item in raw[:4] if str(item).strip()]
    return [QuestionCompetency(name="Понимание материала", weight=1)]


def _fingerprint(test_id: str, payload: QuestionGenerationRequest, chunks: list[ChunkScore]) -> str:
    digest = hashlib.sha256()
    digest.update(test_id.encode())
    digest.update(payload.model_dump_json().encode())
    for item in chunks:
        digest.update(item.chunk.id.encode())
        digest.update(hashlib.sha256(item.chunk.text.encode("utf-8")).digest())
    return digest.hexdigest()


def _token_budget(chunks: list[ChunkScore]) -> int:
    return sum(_estimate_tokens(item.chunk.text) for item in chunks)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _words(text: str) -> list[str]:
    return re.findall(r"[\wа-яА-ЯёЁ-]+", text.lower())


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[i] * right[i] for i in range(size))
    left_norm = sum(left[i] * left[i] for i in range(size)) ** 0.5
    right_norm = sum(right[i] * right[i] for i in range(size)) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
