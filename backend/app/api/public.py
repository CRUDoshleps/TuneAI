import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_token, hash_password
from app.db.session import get_db
from app.models import Assignment, Material, MaterialIndexStatusEnum, Question, RoleEnum, Test, TestStatusEnum, TestTypeEnum, User
from app.schemas import DemoBootstrapRead, DemoBootstrapRequest, PublicConfigRead, TokenPair, UserRead
from app.api.tests import _serialize_test
from app.services.demo_cleanup import cleanup_expired_demo_data, demo_expiration, recent_demo_user_count
from app.services.moderation import censor_text
from app.services.outbox import MATERIAL_UPLOADED, add_outbox_event


router = APIRouter(prefix="/public", tags=["public"])


@router.get("/config", response_model=PublicConfigRead)
def public_config() -> PublicConfigRead:
    settings = get_settings()
    template = _public_value(settings.tuneai_template, "unconfigured")
    product_fallback = "TuneAI" if template == "official" else "Self-host Test Platform"
    logo_fallback = "TuneAI" if template == "official" else "Demo"
    env_theme = _public_theme(settings)
    config: dict[str, Any] = {
        "template": template,
        "productName": _public_value(settings.tuneai_product_name, product_fallback),
        "logoText": _public_value(settings.tuneai_logo_text, logo_fallback),
        "logoUrl": _public_optional_value(settings.tuneai_logo_url),
        "repositoryUrl": _public_value(settings.tuneai_repository_url, "https://github.com/CRUDoshleps/TuneAI"),
        "docsUrl": _public_value(settings.tuneai_docs_url, "https://github.com/CRUDoshleps/TuneAI"),
        "consultationEmail": _public_value(settings.tuneai_consultation_email, "admin@example.com"),
        "consultationPerson": _public_value(settings.tuneai_consultation_person, "Implementation owner"),
    }
    if env_theme:
        config["theme"] = env_theme
    if settings.tuneai_config_json:
        try:
            loaded = json.loads(settings.tuneai_config_json)
            if isinstance(loaded, dict):
                config.update(loaded)
                json_theme = loaded.get("theme")
                if isinstance(json_theme, dict) or env_theme:
                    config["theme"] = {
                        **({key: value for key, value in json_theme.items() if isinstance(value, str) and value.strip()} if isinstance(json_theme, dict) else {}),
                        **env_theme,
                    }
        except json.JSONDecodeError:
            pass
    # This capability is controlled by the server and must not be spoofed by
    # branding JSON. The frontend uses it to avoid advertising a disabled flow.
    config["demoBootstrapEnabled"] = settings.demo_bootstrap_enabled
    return PublicConfigRead(config=config)


def _public_value(value: str | None, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _public_optional_value(value: str | None) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _public_theme(settings: Any) -> dict[str, str]:
    theme = {
        "background": settings.tuneai_background_color,
        "surface": settings.tuneai_surface_color,
        "panel": settings.tuneai_panel_color,
        "panelSoft": settings.tuneai_panel_soft_color,
        "text": settings.tuneai_text_color,
        "muted": settings.tuneai_muted_color,
        "line": settings.tuneai_line_color,
        "accent": settings.tuneai_accent_color,
        "accentSoft": settings.tuneai_accent_soft_color,
        "danger": settings.tuneai_danger_color,
        "warning": settings.tuneai_warning_color,
        "success": settings.tuneai_success_color,
    }
    return {key: value.strip() for key, value in theme.items() if isinstance(value, str) and value.strip()}


@router.post("/demo/bootstrap", response_model=DemoBootstrapRead, status_code=status.HTTP_201_CREATED)
async def demo_bootstrap(
    payload: DemoBootstrapRequest,
    db: Session = Depends(get_db),
) -> DemoBootstrapRead:
    settings = get_settings()
    if not settings.demo_bootstrap_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo bootstrap is disabled")
    cleanup_expired_demo_data(db)
    if recent_demo_user_count(db) >= settings.demo_bootstrap_limit_per_hour:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demo bootstrap limit exceeded")

    stamp = int(time.time() * 1000)
    role = _demo_role(payload.test_type)
    expires_at = demo_expiration(settings.demo_bootstrap_ttl_hours)
    user = User(
        email=f"demo-{payload.scenario_id}-{stamp}@tuneai.dev",
        full_name=f"{payload.role_label} демо",
        hashed_password=hash_password("password123"),
        role=role,
        is_demo=True,
        expires_at=expires_at,
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
        is_demo=True,
        expires_at=expires_at,
    )
    test.questions.append(
        Question(
            text=censor_text(payload.question),
            expected_answer=censor_text(payload.expected_answer),
            competencies=[{"name": item, "weight": 1} for item in payload.competencies],
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
        index_status=MaterialIndexStatusEnum.pending,
    )
    db.add(material)
    db.flush()
    add_outbox_event(db, MATERIAL_UPLOADED, material.id, {"material_id": material.id, "test_id": test.id})
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
