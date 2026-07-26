from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Answer, AnswerStatusEnum, Attempt, AttemptStatusEnum, Question
from app.services.rag import retrieve_context
from app.services.storage import StorageService
from app.services.yandex import YandexAIClient


async def process_answer_uploaded(
    db: Session,
    *,
    answer_id: str,
    storage: StorageService | None = None,
    ai: YandexAIClient | None = None,
) -> Answer:
    answer = db.get(Answer, answer_id)
    if answer is None:
        raise ValueError(f"Answer {answer_id} not found")
    if answer.status == AnswerStatusEnum.completed:
        return answer
    if not answer.audio_object_key:
        answer.status = AnswerStatusEnum.failed
        answer.error_message = "Audio object key is missing"
        db.commit()
        return answer

    storage = storage or StorageService()
    ai = ai or YandexAIClient()
    attempt = db.get(Attempt, answer.attempt_id)
    question = db.get(Question, answer.question_id)
    if attempt is None or question is None:
        raise ValueError("Attempt or question is missing")

    try:
        attempt.status = AttemptStatusEnum.processing
        answer.status = AnswerStatusEnum.transcribing
        answer.error_message = None
        db.commit()

        audio = storage.read_audio(answer.audio_object_key)
        transcript = await ai.transcribe_audio(audio, answer.audio_content_type)
        answer.transcript = transcript
        answer.status = AnswerStatusEnum.transcribed
        db.commit()

        answer.status = AnswerStatusEnum.rag_processing
        db.commit()
        context = await retrieve_context(
            db,
            test_id=attempt.test_id,
            query=f"{question.text}\n{transcript}",
            limit=5,
            ai=ai,
        )

        answer.status = AnswerStatusEnum.evaluating
        db.commit()
        result = await ai.evaluate_answer(
            question=question.text,
            expected_answer=question.expected_answer,
            transcript=transcript,
            criteria=attempt.test.criteria,
            rag_context=context,
            max_score=question.max_score,
        )
        result.source_excerpts = context[:3]
        result.grounded = bool(context)
        result.review_recommended = (
            result.confidence < ai.settings.review_confidence_threshold or not result.grounded
        )
        answer.evaluation = result.model_dump()
        answer.score = result.score
        answer.max_score = result.max_score
        answer.status = AnswerStatusEnum.completed
        db.commit()
        _refresh_attempt_totals(db, attempt)
        db.commit()
        return answer
    except Exception as exc:
        answer.status = AnswerStatusEnum.failed
        answer.error_message = str(exc)[:4000]
        attempt.status = AttemptStatusEnum.failed
        db.add(answer)
        db.add(attempt)
        db.commit()
        return answer


def _refresh_attempt_totals(db: Session, attempt: Attempt) -> None:
    answers = list(db.scalars(select(Answer).where(Answer.attempt_id == attempt.id)).all())
    if not answers:
        return
    if any(answer.status != AnswerStatusEnum.completed for answer in answers):
        return
    attempt.total_score = sum(
        answer.review_score if answer.review_score is not None else (answer.score or 0)
        for answer in answers
    )
    attempt.max_score = sum(answer.max_score or 0 for answer in answers)
    attempt.status = AttemptStatusEnum.completed
    attempt.completed_at = datetime.now(timezone.utc)
    db.add(attempt)

