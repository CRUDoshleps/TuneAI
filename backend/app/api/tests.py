from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import can_create_tests, get_current_user
from app.models import Assignment, Question, RoleEnum, Test, TestStatusEnum, TestTypeEnum, User
from app.schemas import AssignRequest, QuestionCreate, QuestionRead, TestCreate, TestRead, TestUpdate


router = APIRouter(prefix="/tests", tags=["tests"])


@router.get("", response_model=list[TestRead])
def list_tests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    rows = list(db.scalars(select(Test).options(selectinload(Test.questions))).all())
    return [_serialize_test(test, user) for test in rows if _can_view_test(db, test, user)]


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
        title=payload.title,
        description=payload.description,
        test_type=payload.test_type,
        criteria=payload.criteria,
        time_limit_seconds=payload.time_limit_seconds,
        owner_id=user.id,
    )
    for question in payload.questions:
        test.questions.append(
            Question(
                text=question.text,
                expected_answer=question.expected_answer,
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
    if not _can_view_test(db, test, user):
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
        text=payload.text,
        expected_answer=payload.expected_answer,
        order_index=payload.order_index,
        max_score=payload.max_score,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


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


def _load_test(db: Session, test_id: str) -> Test:
    test = db.scalar(select(Test).where(Test.id == test_id).options(selectinload(Test.questions)))
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    test.questions.sort(key=lambda item: item.order_index)
    return test


def _can_view_test(db: Session, test: Test, user: User) -> bool:
    if user.role == RoleEnum.admin or test.owner_id == user.id:
        return True
    if (
        user.role == RoleEnum.student
        and test.status == TestStatusEnum.published
        and test.test_type == TestTypeEnum.self_training
    ):
        return True
    assignment = db.scalar(select(Assignment).where(Assignment.test_id == test.id, Assignment.user_id == user.id))
    return assignment is not None


def _can_manage_test(test: Test, user: User) -> bool:
    return user.role == RoleEnum.admin or test.owner_id == user.id


def _serialize_test(test: Test, user: User) -> dict:
    questions = sorted(test.questions, key=lambda item: item.order_index)
    can_manage = _can_manage_test(test, user)
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
    if not _can_manage_test(test, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner or admin can manage this test")
