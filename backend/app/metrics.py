from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response


REQUESTS = Counter("tuneai_http_requests_total", "HTTP requests", ["method", "path", "status"])
ANSWERS_CREATED = Counter("tuneai_answers_created_total", "Created answer uploads")
ANSWERS_COMPLETED = Counter("tuneai_answers_completed_total", "Completed answer processing jobs")
ANSWERS_FAILED = Counter("tuneai_answers_failed_total", "Failed answer processing jobs")
YANDEX_ERRORS = Counter("tuneai_yandex_errors_total", "Yandex API errors", ["operation"])
TRANSCRIPTION_SECONDS = Histogram("tuneai_transcription_seconds", "Speech-to-text duration")
EVALUATION_SECONDS = Histogram("tuneai_evaluation_seconds", "LLM evaluation duration")


def metrics_response() -> Response:
    return Response(generate_latest(), media_type="text/plain; version=0.0.4")

