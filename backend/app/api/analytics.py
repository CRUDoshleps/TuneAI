from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import can_review_answers, get_current_user
from app.models import Answer, AnswerStatusEnum, Attempt, RoleEnum, Test, User
from app.schemas import CompetencyMetricRead
from app.services.access_control import can_manage_test


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/competencies", response_model=list[CompetencyMetricRead])
def competency_metrics(
    test_id: str | None = None,
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CompetencyMetricRead]:
    stmt = (
        select(Attempt)
        .options(selectinload(Attempt.answers).selectinload(Answer.question), selectinload(Attempt.test))
        .order_by(Attempt.started_at.desc())
        .limit(500)
    )
    if test_id:
        stmt = stmt.where(Attempt.test_id == test_id)
    if user_id:
        stmt = stmt.where(Attempt.user_id == user_id)
    elif not can_review_answers(user) and user.role != RoleEnum.admin:
        stmt = stmt.where(Attempt.user_id == user.id)

    attempts = list(db.scalars(stmt).all())
    stats: dict[str, dict[str, object]] = {}
    for attempt in attempts:
        if not _can_view_attempt_analytics(attempt, user):
            continue
        answers = [answer for answer in attempt.answers if answer.status == AnswerStatusEnum.completed]
        for answer in answers:
            evaluation = answer.evaluation or {}
            competencies = _answer_competencies(answer, attempt.test)
            competency_scores = evaluation.get("competency_scores") or {}
            competency_max_scores = evaluation.get("competency_max_scores") or {}
            for competency in competencies:
                row = stats.setdefault(
                    competency,
                    {"score": 0.0, "max_score": 0.0, "completed": 0, "recommendations": []},
                )
                score = float(competency_scores.get(competency, answer.score or 0))
                max_score = float(competency_max_scores.get(competency, answer.max_score or 0))
                row["score"] = float(row["score"]) + score
                row["max_score"] = float(row["max_score"]) + max_score
                row["completed"] = int(row["completed"]) + 1
                recommendation = str(evaluation.get("recommendations") or "").strip()
                if recommendation and recommendation not in row["recommendations"]:
                    cast_recommendations = row["recommendations"]
                    assert isinstance(cast_recommendations, list)
                    cast_recommendations.append(recommendation)

    return [
        CompetencyMetricRead(
            name=name,
            score=round(float(row["score"]), 2),
            max_score=round(float(row["max_score"]), 2),
            completed_answers=int(row["completed"]),
            recommendations=list(row["recommendations"])[:5],
        )
        for name, row in sorted(stats.items())
    ]


def _can_view_attempt_analytics(attempt: Attempt, user: User) -> bool:
    if attempt.user_id == user.id or user.role == RoleEnum.admin:
        return True
    return can_review_answers(user) and can_manage_test(attempt.test, user)


def _test_competencies(test: Test) -> list[str]:
    raw = test.criteria.get("competencies") if test.criteria else None
    if isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
        if values:
            return values
    return ["Общие навыки"]


def _answer_competencies(answer: Answer, test: Test) -> list[str]:
    values = [
        str(item.get("name", "")).strip()
        for item in (answer.question.competencies or [])
        if str(item.get("name", "")).strip()
    ]
    if values:
        return values
    return _test_competencies(test)
