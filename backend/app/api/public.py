import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_token, hash_password
from app.db.session import get_db
from app.models import Assignment, Material, Question, RoleEnum, Test, TestStatusEnum, TestTypeEnum, User
from app.schemas import DemoBootstrapRead, DemoBootstrapRequest, PublicConfigRead, TokenPair, UserRead
from app.api.tests import _serialize_test
from app.services.moderation import censor_text
from app.services.rag import create_material_chunks
from app.services.yandex import YandexAIClient


router = APIRouter(prefix="/public", tags=["public"])


@router.get("/config", response_model=PublicConfigRead)
def public_config() -> PublicConfigRead:
    settings = get_settings()
    config: dict[str, Any] = {
        "template": settings.tuneai_template,
        "productName": settings.tuneai_product_name,
        "logoText": settings.tuneai_logo_text,
        "logoUrl": settings.tuneai_logo_url,
        "repositoryUrl": settings.tuneai_repository_url,
        "docsUrl": settings.tuneai_docs_url,
        "consultationEmail": settings.tuneai_consultation_email,
        "consultationPerson": settings.tuneai_consultation_person,
    }
    if settings.tuneai_config_json:
        try:
            loaded = json.loads(settings.tuneai_config_json)
            if isinstance(loaded, dict):
                config.update(loaded)
        except json.JSONDecodeError:
            pass
    return PublicConfigRead(config=config)


@router.post("/demo/bootstrap", response_model=DemoBootstrapRead, status_code=status.HTTP_201_CREATED)
async def demo_bootstrap(
    payload: DemoBootstrapRequest,
    db: Session = Depends(get_db),
) -> DemoBootstrapRead:
    settings = get_settings()
    if not settings.demo_bootstrap_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo bootstrap is disabled")

    stamp = int(time.time() * 1000)
    role = _demo_role(payload.test_type)
    user = User(
        email=f"demo-{payload.scenario_id}-{stamp}@tuneai.dev",
        full_name=f"{payload.role_label} демо",
        hashed_password=hash_password("password123"),
        role=role,
    )
    db.add(user)
    db.flush()
    owner = user if payload.test_type == TestTypeEnum.self_training else _ensure_demo_owner(db, payload.test_type)

    test = Test(
        title=censor_text(f"Демо: {payload.label}"),
        description=censor_text(payload.description),
        test_type=payload.test_type,
        status=TestStatusEnum.published,
        criteria={
            "rubric": "Оценить корректность, полноту, аргументацию и опору на материалы.",
            "competencies": payload.competencies,
            "scenario": payload.test_type.value,
            "agent_profile": payload.agent_profile,
            "review_confidence_threshold": 0.78,
            "strictness": "balanced",
            "material_policy": "test_and_question",
        },
        owner_id=owner.id,
    )
    test.questions.append(
        Question(
            text=censor_text(payload.question),
            expected_answer=censor_text(payload.expected_answer),
            order_index=0,
            max_score=10,
        )
    )
    db.add(test)
    db.flush()
    question = test.questions[0]
    material = Material(
        test_id=test.id,
        question_id=question.id,
        owner_id=owner.id,
        title=censor_text(f"Материал: {payload.label}"),
        content=(
            f"{payload.expected_answer} RAG извлекает релевантные фрагменты из материалов "
            "и связывает обратную связь с контекстом сценария."
        ),
    )
    db.add(material)
    db.flush()
    await create_material_chunks(db, material, YandexAIClient())
    if payload.test_type != TestTypeEnum.self_training:
        db.add(Assignment(test_id=test.id, user_id=user.id, created_by_id=owner.id))
    db.commit()
    db.refresh(user)
    db.refresh(test)

    tokens = TokenPair(access_token=create_token(user.id, "access"), refresh_token=create_token(user.id, "refresh"))
    return DemoBootstrapRead(tokens=tokens, user=UserRead.model_validate(user), test=_serialize_test(test, user))


def _demo_role(test_type: TestTypeEnum) -> RoleEnum:
    if test_type == TestTypeEnum.exam:
        return RoleEnum.examinee
    if test_type == TestTypeEnum.interview:
        return RoleEnum.candidate
    return RoleEnum.student


def _ensure_demo_owner(db: Session, test_type: TestTypeEnum) -> User:
    if test_type == TestTypeEnum.interview:
        role = RoleEnum.interviewer
        email = "demo-interviewer-owner@tuneai.dev"
        name = "Demo Interviewer Owner"
    else:
        role = RoleEnum.methodist
        email = "demo-methodist-owner@tuneai.dev"
        name = "Demo Methodist Owner"
    user = db.query(User).filter(User.email == email).one_or_none()
    if user:
        return user
    user = User(email=email, full_name=name, hashed_password=hash_password("password123"), role=role)
    db.add(user)
    db.flush()
    return user
