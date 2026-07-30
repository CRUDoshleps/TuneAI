from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_roles
from app.models import AIProviderConfig, AIProviderEnum, RoleEnum, User
from app.schemas import AIProviderConfigCreate, AIProviderConfigRead, AIProviderConfigUpdate


router = APIRouter(prefix="/admin/ai-providers", tags=["admin"])


@router.get("", response_model=list[AIProviderConfigRead])
def list_ai_providers(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> list[AIProviderConfigRead]:
    rows = db.scalars(select(AIProviderConfig).order_by(AIProviderConfig.created_at.desc())).all()
    return [_serialize_provider(row) for row in rows]


@router.post("", response_model=AIProviderConfigRead, status_code=status.HTTP_201_CREATED)
def create_ai_provider(
    payload: AIProviderConfigCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(RoleEnum.admin)),
) -> AIProviderConfigRead:
    profile = AIProviderConfig(
        name=payload.name.strip(),
        provider=payload.provider,
        is_enabled=payload.is_enabled,
        is_active=False,
        credentials=_clean_credentials(payload.credentials),
        config=_clean_config(payload.provider, payload.config),
        created_by_id=user.id,
    )
    db.add(profile)
    db.flush()
    if payload.is_active:
        _activate_provider(db, profile)
    db.commit()
    db.refresh(profile)
    return _serialize_provider(profile)


@router.patch("/{provider_id}", response_model=AIProviderConfigRead)
def update_ai_provider(
    provider_id: str,
    payload: AIProviderConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> AIProviderConfigRead:
    profile = db.get(AIProviderConfig, provider_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provider config not found")
    if payload.name is not None:
        profile.name = payload.name.strip()
    if payload.is_enabled is not None:
        profile.is_enabled = payload.is_enabled
        if not profile.is_enabled:
            profile.is_active = False
    if payload.credentials is not None:
        profile.credentials = _merge_credentials(profile.credentials or {}, payload.credentials)
    if payload.config is not None:
        profile.config = _clean_config(profile.provider, payload.config)
    if payload.is_active is not None:
        if payload.is_active:
            _activate_provider(db, profile)
        else:
            profile.is_active = False
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _serialize_provider(profile)


@router.post("/{provider_id}/activate", response_model=AIProviderConfigRead)
def activate_ai_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> AIProviderConfigRead:
    profile = db.get(AIProviderConfig, provider_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provider config not found")
    _activate_provider(db, profile)
    db.commit()
    db.refresh(profile)
    return _serialize_provider(profile)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ai_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.admin)),
) -> None:
    profile = db.get(AIProviderConfig, provider_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI provider config not found")
    db.delete(profile)
    db.commit()


def _activate_provider(db: Session, profile: AIProviderConfig) -> None:
    if not profile.is_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Disabled AI provider cannot be activated")
    _validate_ready(profile)
    for row in db.scalars(select(AIProviderConfig).where(AIProviderConfig.id != profile.id)).all():
        row.is_active = False
        db.add(row)
    profile.is_active = True
    db.add(profile)


def _validate_ready(profile: AIProviderConfig) -> None:
    credentials = profile.credentials or {}
    config = profile.config or {}
    if profile.provider == AIProviderEnum.mock:
        return
    if profile.provider == AIProviderEnum.yandex:
        if not (credentials.get("api_key") or credentials.get("iam_token")):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Yandex credentials are required")
        if not credentials.get("folder_id"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Yandex folder ID is required")
    if profile.provider in {AIProviderEnum.openai_compatible, AIProviderEnum.local}:
        if not credentials.get("api_key"):
            if profile.provider == AIProviderEnum.openai_compatible:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="OpenAI-compatible API key is required")
        if not (config.get("base_url") or config.get("chat_completion_url")):
            detail = "Local model endpoint is required" if profile.provider == AIProviderEnum.local else "OpenAI-compatible base URL is required"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
        if not (config.get("base_url") or config.get("embedding_url")):
            detail = "Local model embedding endpoint is required" if profile.provider == AIProviderEnum.local else "OpenAI-compatible embedding URL is required"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _clean_credentials(credentials: dict[str, str | None]) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in credentials.items():
        normalized = str(key).strip()
        if not normalized or value is None:
            continue
        text = str(value).strip()
        if text:
            clean[normalized] = text
    return clean


def _merge_credentials(current: dict[str, str], updates: dict[str, str | None]) -> dict[str, str]:
    merged = dict(current)
    for key, value in updates.items():
        normalized = str(key).strip()
        if not normalized:
            continue
        if value is None:
            merged.pop(normalized, None)
            continue
        text = str(value).strip()
        if text:
            merged[normalized] = text
    return merged


def _clean_config(provider: AIProviderEnum, config: dict[str, object]) -> dict[str, object]:
    clean = {str(key).strip(): value for key, value in config.items() if str(key).strip()}
    if provider in {AIProviderEnum.openai_compatible, AIProviderEnum.local} and clean.get("base_url"):
        clean["base_url"] = str(clean["base_url"]).strip().rstrip("/")
    return clean


def _serialize_provider(profile: AIProviderConfig) -> AIProviderConfigRead:
    return AIProviderConfigRead(
        id=profile.id,
        name=profile.name,
        provider=profile.provider,
        is_enabled=profile.is_enabled,
        is_active=profile.is_active,
        credentials_masked={key: _mask_secret(value) for key, value in (profile.credentials or {}).items()},
        config=profile.config or {},
        created_by_id=profile.created_by_id,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _mask_secret(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 8:
        return "••••"
    return f"{text[:2]}••••{text[-4:]}"
