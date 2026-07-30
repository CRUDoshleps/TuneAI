from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import can_create_tests, get_current_user
from app.models import Answer, Assignment, Attempt, Question, RoleEnum, Test, TestTypeEnum, User
from app.schemas import AssignRequest, QuestionCreate, QuestionRead, QuestionReorderRequest, QuestionUpdate, TestCreate, TestRead, TestUpdate
from app.services.moderation import censor_content, censor_text
from app.services.access_control import can_manage_test, can_view_test


router = APIRouter(prefix="/tests", tags=["tests"])


@router.get("", response_model=list[TestRead])
def list_tests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    rows = list(db.scalars(select(Test).options(selectinload(Test.questions))).all())
    return [_serialize_test(test, user) for test in rows if can_view_test(db, test, user)]


@router.post("", response_model=TestRead, status_code=status.HTTP_201_CREATED)
def create_test(
    payload: TestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not can_create_tests(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only self-training users and staff users can create tests",
        )
    if user.role == RoleEnum.student and payload.test_type != TestTypeEnum.self_training:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-training users can create only self-training tests",
        )
    test = Test(
        title=censor_text(payload.title),
        description=censor_text(payload.description),
        test_type=payload.test_type,
        criteria=censor_content(payload.criteria),
        time_limit_seconds=payload.time_limit_seconds,
        owner_id=user.id,
    )
    for question in payload.questions:
        test.questions.append(
            Question(
                text=censor_text(question.text),
                expected_answer=censor_text(question.expected_answer),
                order_index=question.order_index,
                max_score=question.max_score,
            )
        )
    db.add(test)
    db.commit()
    db.refresh(test)
    return _serialize_test(_load_test(db, test.id), user)


@router.get("/{test_id}", response_model=TestRead)
def get_test(
    test_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    test = _load_test(db, test_id)
    if not can_view_test(db, test, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return _serialize_test(test, user)


@router.patch("/{test_id}", response_model=TestRead)
def update_test(
    test_id: str,
    payload: TestUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    test = _load_test(db, test_id)
    _ensure_manager(test, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field in {"title", "description"} and value is not None:
            value = censor_text(value)
        elif field == "criteria" and value is not None:
            value = censor_content(value)
        setattr(test, field, value)
    db.add(test)
    db.commit()
    return _serialize_test(_load_test(db, test.id), user)


@router.post("/{test_id}/questions", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
def add_question(
    test_id: str,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Question:
    test = _load_test(db, test_id)
    _ensure_manager(test, user)
    question = Question(
        test_id=test.id,
        text=censor_text(payload.text),
        expected_answer=censor_text(payload.expected_answer),
        order_index=payload.order_index,
        max_score=payload.max_score,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.patch("/{test_id}/questions/{question_id}", response_model=QuestionRead)
def update_question(
    test_id: str,
    question_id: str,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Question:
    test = _load_test(db, test_id)
    _ensure_manager(test, user)
    question = db.get(Question, question_id)
    if not question or question.test_id != test.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in this test")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field in {"text", "expected_answer"} and value is not None:
            value = censor_text(value)
        setattr(question, field, value)
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.delete("/{test_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    test_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    test = _load_test(db, test_id)
    _ensure_manager(test, user)
    question = db.get(Question, question_id)
    if not question or question.test_id != test.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in this test")
    answers_count = db.scalar(select(func.count(Answer.id)).where(Answer.question_id == question.id)) or 0
    if answers_count:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Question has answers and cannot be deleted")
    db.delete(question)
    db.commit()


@router.post("/{test_id}/questions/reorder", response_model=TestRead)
def reorder_questions(
    test_id: str,
    payload: QuestionReorderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    test = _load_test(db, test_id)
    _ensure_manager(test, user)
    current_ids = {question.id for question in test.questions}
    requested_ids = set(payload.question_ids)
    if current_ids != requested_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Question order must include every question")
    by_id = {question.id: question for question in test.questions}
    for index, question in enumerate(test.questions):
        question.order_index = -(index + 1)
        db.add(question)
    db.flush()
    for index, question_id in enumerate(payload.question_ids):
        by_id[question_id].order_index = index
        db.add(by_id[question_id])
    db.commit()
    return _serialize_test(_load_test(db, test.id), user)


@router.post("/{test_id}/assign", status_code=status.HTTP_204_NO_CONTENT)
def assign_test(
    test_id: str,
    payload: AssignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    test = _load_test(db, test_id)
    _ensure_manager(test, user)
    target = db.get(User, payload.user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")
    db.add(Assignment(test_id=test.id, user_id=target.id, created_by_id=user.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already assigned") from None


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test(
    test_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    test = _load_test(db, test_id)
    _ensure_manager(test, user)
    attempts_count = db.scalar(select(func.count(Attempt.id)).where(Attempt.test_id == test.id)) or 0
    if attempts_count:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Test has attempts and cannot be deleted")
    db.delete(test)
    db.commit()


def _load_test(db: Session, test_id: str) -> Test:
    test = db.scalar(select(Test).where(Test.id == test_id).options(selectinload(Test.questions)))
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    test.questions.sort(key=lambda item: item.order_index)
    return test


def _serialize_test(test: Test, user: User) -> dict:
    questions = sorted(test.questions, key=lambda item: item.order_index)
    can_manage = can_manage_test(test, user)
    return {
        "id": test.id,
        "title": test.title,
        "description": test.description,
        "test_type": test.test_type,
        "status": test.status,
        "criteria": test.criteria,
        "time_limit_seconds": test.time_limit_seconds,
        "owner_id": test.owner_id,
        "created_at": test.created_at,
        "question_count": len(questions),
        "questions": questions if can_manage else [],
    }


def _ensure_manager(test: Test, user: User) -> None:
    if not can_manage_test(test, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner or admin can manage this test")
