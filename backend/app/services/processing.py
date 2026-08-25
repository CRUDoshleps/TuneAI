from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Answer, AnswerStatusEnum, AnswerTypeEnum, Attempt, AttemptStatusEnum, Question
from app.services.ai_provider_runtime import TuneAIClient, get_active_ai_client
from app.services.ai_skills import load_skill_instructions
from app.services.ai_safety import build_trusted_evaluation_inputs, detect_suspicious_ai_input
from app.services.rag import retrieve_context
from app.services.storage import StorageService


async def process_answer_uploaded(
    db: Session,
    *,
    answer_id: str,
    storage: StorageService | None = None,
    ai: TuneAIClient | None = None,
) -> Answer:
    answer = db.get(Answer, answer_id)
    if answer is None:
        raise ValueError(f"Answer {answer_id} not found")
    if answer.status == AnswerStatusEnum.completed:
        return answer
    if answer.answer_type == AnswerTypeEnum.audio and not answer.audio_object_key:
        answer.status = AnswerStatusEnum.failed
        answer.error_message = "Audio object key is missing"
        db.commit()
        return answer
    if answer.answer_type == AnswerTypeEnum.text and not answer.text_response:
        answer.status = AnswerStatusEnum.failed
        answer.error_message = "Text response is missing"
        db.commit()
        return answer

    storage = storage or StorageService()
    ai = ai or get_active_ai_client(db)
    attempt = db.get(Attempt, answer.attempt_id)
    question = db.get(Question, answer.question_id)
    if attempt is None or question is None:
        raise ValueError("Attempt or question is missing")

    try:
        attempt.status = AttemptStatusEnum.processing
        answer.status = AnswerStatusEnum.transcribing if answer.answer_type == AnswerTypeEnum.audio else AnswerStatusEnum.transcribed
        answer.error_message = None
        db.commit()

        if answer.answer_type == AnswerTypeEnum.audio:
            audio = storage.read_audio(answer.audio_object_key or "")
            transcript = await ai.transcribe_audio(audio, answer.audio_content_type)
        else:
            transcript = answer.text_response or ""
        answer.transcript = transcript
        answer.status = AnswerStatusEnum.transcribed
        db.commit()

        answer.status = AnswerStatusEnum.rag_processing
        db.commit()
        context = await retrieve_context(
            db,
            test_id=attempt.test_id,
            question_id=question.id,
            query=f"{question.text}\n{transcript}",
            limit=5,
            material_policy=str((attempt.test.criteria or {}).get("material_policy") or "test_and_question"),
            ai=ai,
        )
        safety = detect_suspicious_ai_input(
            transcript=transcript,
            expected_answer=question.expected_answer,
            rag_context=context,
        )
        trusted_inputs = build_trusted_evaluation_inputs(
            question=question.text,
            expected_answer=question.expected_answer,
            transcript=transcript,
            criteria=attempt.test.criteria,
            rag_context=context,
        )

        answer.status = AnswerStatusEnum.evaluating
        db.commit()
        skill_instructions = load_skill_instructions(db, attempt.test.criteria)
        result = await ai.evaluate_answer(
            question=trusted_inputs["question"],
            expected_answer=trusted_inputs["expected_answer"],
            transcript=trusted_inputs["transcript"],
            criteria=trusted_inputs["criteria"],
            rag_context=trusted_inputs["rag_context"],
            max_score=question.max_score,
            ai_skill_instructions=skill_instructions,
        )
        result.source_excerpts = context[:3]
        competency_scores, competency_max_scores = _competency_scores(question, attempt.test.criteria, result.score, result.max_score)
        result.competency_scores = competency_scores
        result.grounded = bool(context)
        result.review_recommended = (
            result.confidence < ai.settings.review_confidence_threshold or not result.grounded or safety.detected
        )
        payload = result.model_dump()
        payload["competency_max_scores"] = competency_max_scores
        payload["ai_safety"] = safety.model_dump()
        if skill_instructions:
            payload["ai_skill_instructions_applied"] = True
        answer.evaluation = payload
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
    question_count = len(list(db.scalars(select(Question.id).where(Question.test_id == attempt.test_id)).all()))
    if len(answers) < question_count:
        attempt.status = AttemptStatusEnum.processing
        db.add(attempt)
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


def _competency_scores(question: Question, criteria: dict, score: float, max_score: float) -> tuple[dict[str, float], dict[str, float]]:
    question_competencies = [
        (str(item.get("name", "")).strip(), float(item.get("weight", 1)))
        for item in (question.competencies or [])
        if str(item.get("name", "")).strip() and float(item.get("weight", 1)) > 0
    ]
    if question_competencies:
        total_weight = sum(weight for _, weight in question_competencies)
        return (
            {name: round(score * weight / total_weight, 2) for name, weight in question_competencies},
            {name: round(max_score * weight / total_weight, 2) for name, weight in question_competencies},
        )
    raw = criteria.get("competencies") if criteria else None
    if not isinstance(raw, list):
        return {}, {}
    competencies = [str(item).strip() for item in raw if str(item).strip()]
    if not competencies:
        return {}, {}
    per_competency = round(score / len(competencies), 2)
    per_competency_max = round(max_score / len(competencies), 2)
    return (
        {competency: per_competency for competency in competencies},
        {competency: per_competency_max for competency in competencies},
    )
