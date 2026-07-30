import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import admin, admin_ai, analytics, attempts, auth, materials, moodle, public, skills, tests, users
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal, get_db, init_db
from app.metrics import REQUESTS, metrics_response
from app.schemas import AIReadiness
from app.services.ai_provider_runtime import active_provider_readiness


configure_logging()
settings = get_settings()
logger = structlog.get_logger("tuneai.api")
rate_windows: dict[str, deque[float]] = defaultdict(deque)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_production()
    if settings.init_db_on_startup:
        init_db()
    yield


app = FastAPI(
    title="TuneAI",
    description="Secure oral testing platform backed by Yandex AI Studio.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.normalized_cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=settings.effective_cors_allow_credentials,
    allow_methods=["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next: Callable) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    start = time.perf_counter()
    status_code = 500
    try:
        if _is_rate_limited(request):
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
            return JSONResponse({"detail": "Too many requests"}, status_code=status_code)
        response = await call_next(request)
        status_code = response.status_code
        response.headers["x-request-id"] = request_id
        return response
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        REQUESTS.labels(request.method, request.url.path, str(status_code)).inc()
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        structlog.contextvars.clear_contextvars()


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readiness", tags=["system"])
def readiness() -> dict[str, str]:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/readiness/ai", response_model=AIReadiness, tags=["system"])
def ai_readiness(db: Session = Depends(get_db)) -> AIReadiness:
    db_readiness = active_provider_readiness(db, settings)
    if db_readiness:
        return db_readiness
    has_credentials = bool(settings.yandex_api_key or settings.yandex_iam_token)
    configured = settings.yandex_mock or bool(has_credentials and settings.yandex_folder_id)
    mode = "mock" if settings.yandex_mock else "real"
    disclosure = (
        "Демонстрационный режим: ответы AI воспроизводимы и не отправляются во внешние модели."
        if settings.yandex_mock
        else "Рабочий режим: аудио и текст обрабатываются сервисами Yandex AI Studio."
    )
    provider = "Mock AI" if settings.yandex_mock else "Yandex AI Studio"
    return AIReadiness(
        status="ready" if configured else "configuration_required",
        mode=mode,
        configured=configured,
        provider=provider,
        capabilities=["Mock evaluation", "RAG"] if settings.yandex_mock else ["SpeechKit STT", "YandexGPT", "Text Embeddings", "RAG"],
        review_confidence_threshold=settings.review_confidence_threshold,
        disclosure=disclosure,
    )


if settings.metrics_enabled:
    app.add_api_route("/metrics", metrics_response, methods=["GET"], include_in_schema=False)


app.include_router(auth.router)
app.include_router(public.router)
app.include_router(users.router)
app.include_router(skills.router)
app.include_router(tests.router)
app.include_router(attempts.router)
app.include_router(materials.router)
app.include_router(moodle.router)
app.include_router(admin.router)
app.include_router(admin_ai.router)
app.include_router(analytics.router)


def _is_rate_limited(request: Request) -> bool:
    if request.method == "OPTIONS":
        return False
    if not request.url.path.startswith("/auth/"):
        return False
    now = time.monotonic()
    key = request.client.host if request.client else "unknown"
    window = rate_windows[key]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        return True
    window.append(now)
    return False
