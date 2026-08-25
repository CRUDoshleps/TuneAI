from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import can_create_tests, get_current_user
from app.models import AISkill, Answer, Assignment, Attempt, Group, GroupMembership, Material, Question, RoleEnum, Test, TestStatusEnum, TestTypeEnum, User
from app.schemas import (
    AssignRequest,
    CalibrationPreviewRead,
    CalibrationPreviewRequest,
    CalibrationPreviewItem,
    GroupAssignRead,
    GroupAssignRequest,
    QuestionCreate,
    QuestionGenerationRead,
    QuestionGenerationRequest,
    QuestionRead,
    QuestionReorderRequest,
    QuestionUpdate,
    TestCreate,
    TestRead,
    TestUpdate,
)
from app.services.moderation import censor_content, censor_text
from app.services.access_control import can_manage_test, can_view_test
from app.services.ai_provider_runtime import get_active_ai_client
from app.services.ai_skills import load_skill_instructions, skill_ids_from_criteria
from app.services.question_generation import generate_questions_from_rag
from app.services.rag import retrieve_context


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
        criteria=_validated_criteria(db, payload.criteria, user),
        time_limit_seconds=payload.time_limit_seconds,
        owner_id=user.id,
    )
    for question in payload.questions:
        test.questions.append(
            Question(
                text=censor_text(question.text),
                expected_answer=censor_text(question.expected_answer),
                competencies=[item.model_dump() for item in question.competencies],
                answer_mode=question.answer_mode,
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
            value = _validated_criteria(db, value, user)
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
        competencies=[item.model_dump() for item in payload.competencies],
        answer_mode=payload.answer_mode,
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
        elif field == "competencies" and value is not None:
            value = [{"name": str(item["name"]).strip(), "weight": float(item["weight"])} for item in value]
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
    for material in list(db.scalars(select(Material).where(Material.question_id == question.id)).all()):
        db.delete(material)
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
    if user.role != RoleEnum.admin:
        if target.role not in {RoleEnum.student, RoleEnum.examinee, RoleEnum.candidate} or target.created_by_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only managed learner users can be assigned")
    db.add(Assignment(test_id=test.id, user_id=target.id, created_by_id=user.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already assigned") from None


@router.post("/{test_id}/assign-group", response_model=GroupAssignRead)
def assign_test_group(
    test_id: str,
    payload: GroupAssignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GroupAssignRead:
    test = _load_test(db, test_id)
    _ensure_manager(test, user)
    group = db.scalar(select(Group).where(Group.id == payload.group_id))
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if user.role != RoleEnum.admin and group.created_by_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only managed groups can be assigned")
    member_ids = list(db.scalars(select(GroupMembership.user_id).where(GroupMembership.group_id == group.id)).all())
    if not member_ids:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Group has no members")
    existing_ids = set(db.scalars(select(Assignment.user_id).where(Assignment.test_id == test.id, Assignment.user_id.in_(member_ids))).all())
    assigned_count = 0
    for member_id in member_ids:
        if member_id in existing_ids:
            continue
        db.add(Assignment(test_id=test.id, user_id=member_id, created_by_id=user.id))
        assigned_count += 1
    db.commit()
    return GroupAssignRead(
        group_id=group.id,
        test_id=test.id,
        assigned_count=assigned_count,
        skipped_count=len(member_ids) - assigned_count,
    )


@router.post("/{test_id}/generate-questions", response_model=QuestionGenerationRead)
def generate_questions(
    test_id: str,
    payload: QuestionGenerationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuestionGenerationRead:
    test = _load_test(db, test_id)
    _ensure_manager(test, user)
    if payload.question_id:
        question = db.get(Question, payload.question_id)
        if not question or question.test_id != test.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in this test")
    return generate_questions_from_rag(db, test=test, payload=payload, created_by_id=user.id)


@router.post("/{test_id}/calibration-preview", response_model=CalibrationPreviewRead)
async def calibration_preview(
    test_id: str,
    payload: CalibrationPreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CalibrationPreviewRead:
    test = _load_test(db, test_id)
    _ensure_manager(test, user)
    question = _calibration_question(db, test, payload.question_id)
    criteria = dict(test.criteria or {})
    if payload.skill_id:
        criteria["skill_ids"] = [payload.skill_id]
    criteria = _validated_criteria(db, criteria, user)
    material_policy = str(criteria.get("material_policy") or "test_and_question")
    ai = get_active_ai_client(db)
    skill_instructions = load_skill_instructions(db, criteria)
    context_cache: dict[str, list[str]] = {}
    items: list[CalibrationPreviewItem] = []
    for example in payload.examples:
        context_key = f"{question.id}:{material_policy}"
        if context_key not in context_cache:
            context_cache[context_key] = await retrieve_context(
                db,
                test_id=test.id,
                question_id=question.id,
                query=f"{question.text}\n{example.answer}",
                limit=4,
                material_policy=material_policy,
                ai=ai,
            )
        context = context_cache[context_key]
        result = await ai.evaluate_answer(
            question=question.text,
            expected_answer=question.expected_answer,
            transcript=example.answer,
            criteria=criteria,
            rag_context=context,
            max_score=question.max_score,
            ai_skill_instructions=skill_instructions,
        )
        manual_reason = None
        threshold = _skill_threshold(db, payload.skill_id, float(criteria.get("review_confidence_threshold") or 0.78))
        if result.confidence < threshold:
            manual_reason = f"confidence {result.confidence:.2f} below threshold {threshold:.2f}"
        items.append(
            CalibrationPreviewItem(
                label=example.label,
                score=result.score,
                max_score=result.max_score,
                confidence=result.confidence,
                feedback=result.feedback,
                source_excerpts=context[:3],
                manual_review_reason=manual_reason,
            )
        )
    return CalibrationPreviewRead(
        skill_id=payload.skill_id,
        material_policy=material_policy,
        items=items,
        token_budget_estimate=sum(len(example.answer) // 4 for example in payload.examples) + sum(len(item) // 4 for item in context_cache.get(f"{question.id}:{material_policy}", [])),
        reused_rag_context=True,
    )


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
        test.status = TestStatusEnum.archived
        db.add(test)
        db.commit()
        return
    for material in list(db.scalars(select(Material).where(Material.test_id == test.id)).all()):
        db.delete(material)
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
        "is_demo": test.is_demo,
        "expires_at": test.expires_at,
        "created_at": test.created_at,
        "question_count": len(questions),
        "questions": questions if can_manage else [],
    }


def _validated_criteria(db: Session, criteria: dict, user: User) -> dict:
    payload = censor_content(criteria)
    skill_ids = skill_ids_from_criteria(payload)
    if not skill_ids:
        return payload
    stmt = select(AISkill.id).where(AISkill.id.in_(skill_ids))
    if user.role != RoleEnum.admin:
        stmt = stmt.where(AISkill.owner_id == user.id)
    available_ids = set(db.scalars(stmt).all())
    if set(skill_ids) != available_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI skill is not available for this test")
    payload["skill_ids"] = skill_ids
    return payload


def _calibration_question(db: Session, test: Test, question_id: str | None) -> Question:
    if question_id:
        question = db.get(Question, question_id)
        if question and question.test_id == test.id:
            return question
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in this test")
    if test.questions:
        return sorted(test.questions, key=lambda item: item.order_index)[0]
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Test does not contain questions")


def _skill_threshold(db: Session, skill_id: str | None, fallback: float) -> float:
    if not skill_id:
        return fallback
    skill = db.get(AISkill, skill_id)
    return skill.confidence_threshold if skill else fallback


def _ensure_manager(test: Test, user: User) -> None:
    if not can_manage_test(test, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner or admin can manage this test")
