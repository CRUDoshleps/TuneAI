import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.attempts import start_attempt
from app.core.config import get_settings
from app.core.security import create_token, hash_password
from app.db.session import get_db
from app.deps import get_current_user
from app.models import Answer, AnswerStatusEnum, Assignment, Attempt, RoleEnum, Test, TestStatusEnum, User
from app.schemas import AttemptRead, AttemptStartRequest, TokenPair
from app.services.demo_cleanup import cleanup_expired_demo_data, demo_expiration, recent_demo_user_count
from app.services.meme_quiz import MEME_QUESTIONS, MEME_TEST_ID


router = APIRouter(prefix="/public/memes", tags=["public"])


class MemeSessionRead(BaseModel):
    tokens: TokenPair
    attempt: AttemptRead


def _quiz(db: Session) -> Test:
    if not get_settings().demo_bootstrap_enabled:
        raise HTTPException(status_code=404, detail="Мемный зачёт недоступен")
    test = db.get(Test, MEME_TEST_ID)
    if test is None or test.status != TestStatusEnum.published:
        raise HTTPException(status_code=503, detail="Мемный зачёт ещё не подготовлен")
    return test


@router.get("")
def meme_quiz(db: Session = Depends(get_db)) -> dict:
    test = _quiz(db)
    return {
        "title": test.title,
        "questions": [
            {
                "id": question.id,
                "text": question.text,
                "order_index": question.order_index,
                "image": f'/memes/{MEME_QUESTIONS[question.order_index]["image"]}',
                "alt": MEME_QUESTIONS[question.order_index]["alt"],
                "hint": MEME_QUESTIONS[question.order_index]["hint"],
            }
            for question in sorted(test.questions, key=lambda q: q.order_index)
        ],
    }


@router.post("/start", response_model=MemeSessionRead, status_code=201)
def start_meme_quiz(db: Session = Depends(get_db)) -> MemeSessionRead:
    test = _quiz(db)
    settings = get_settings()
    cleanup_expired_demo_data(db)
    if recent_demo_user_count(db) >= settings.demo_bootstrap_limit_per_hour:
        raise HTTPException(status_code=429, detail="Слишком много участников. Попробуйте чуть позже.")
    user = User(
        email=f"meme-guest-{secrets.token_hex(16)}@tuneai.dev",
        full_name="Участник мемного зачёта",
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        role=RoleEnum.examinee,
        is_demo=True,
        expires_at=demo_expiration(settings.demo_bootstrap_ttl_hours),
    )
    db.add(user)
    db.flush()
    db.add(Assignment(test_id=test.id, user_id=user.id, created_by_id=test.owner_id))
    db.commit()
    attempt = start_attempt(AttemptStartRequest(test_id=test.id), db, user)
    return MemeSessionRead(
        tokens=TokenPair(access_token=create_token(user.id, "access"), refresh_token=create_token(user.id, "refresh")),
        attempt=attempt,
    )


@router.get("/attempts/{attempt_id}/questions/{question_id}/explanation")
def meme_explanation(
    attempt_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.test_id != MEME_TEST_ID or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Попытка не найдена")
    answer = db.query(Answer).filter(Answer.attempt_id == attempt.id, Answer.question_id == question_id).one_or_none()
    if answer is None or answer.status != AnswerStatusEnum.completed:
        raise HTTPException(status_code=409, detail="Сначала дождитесь проверки ответа")
    question = answer.question
    item = MEME_QUESTIONS[question.order_index]
    return {"name": item["name"], "explanation": question.explanation, "expected_answer": question.expected_answer, "source": item["source"]}
