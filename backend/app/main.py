import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin, attempts, auth, materials, tests, users
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import init_db
from app.metrics import REQUESTS, metrics_response


configure_logging()
settings = get_settings()
logger = structlog.get_logger("tuneai.api")
rate_windows: dict[str, deque[float]] = defaultdict(deque)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="TuneAI",
    description="Secure oral testing platform backed by Yandex AI Studio.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.normalized_cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=settings.effective_cors_allow_credentials,
    allow_methods=["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
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
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return metrics_response()


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tests.router)
app.include_router(attempts.router)
app.include_router(materials.router)
app.include_router(admin.router)


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
