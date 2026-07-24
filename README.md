# TuneAI

TuneAI is a secure prototype for automated oral testing and interviews backed by Yandex AI Studio.

The user-facing client records a spoken answer and sends it only to the company or university backend. API keys for Yandex AI Studio never reach the browser. The backend stores the answer, writes an outbox event in the same database transaction, and workers process the answer asynchronously through a message broker.

## What It Does

- User registration and login with JWT access/refresh tokens.
- Role-based access control for `student`, `examinee`, `candidate`, `teacher`, `interviewer`, and `admin`.
- Test/interview creation with questions, criteria, statuses, and time limits.
- Attempt creation and secure audio upload.
- Transactional outbox for reliable queue publishing.
- Worker pipeline for speech-to-text, RAG context retrieval, YandexGPT scoring, and report generation.
- Text material upload and embedding-based RAG search.
- Admin dashboard endpoint with usage and failure counters.
- JSON logs, request IDs, health/readiness endpoints, and Prometheus metrics.
- Docker Compose for PostgreSQL, RabbitMQ, MinIO, backend, worker, frontend, and Prometheus.

## Architecture

```text
Browser / embedded client
  -> FastAPI backend
  -> PostgreSQL + audio storage
  -> outbox_events table
  -> RabbitMQ
  -> worker
  -> Yandex SpeechKit / YandexGPT / Yandex Text Embeddings
  -> PostgreSQL report
  -> Browser polls attempt status
```

The MVP keeps the backend and workers in one Python codebase. The service boundaries are already explicit, so Speech-to-Text, RAG, evaluation, and reporting can later be split into independent services.

## Yandex AI Studio Integration

TuneAI has a mock mode enabled by default:

```env
YANDEX_MOCK=true
```

For real calls, set `YANDEX_MOCK=false`, configure `YANDEX_FOLDER_ID`, and provide either `YANDEX_API_KEY` or `YANDEX_IAM_TOKEN`.

Recommended model configuration:

```env
YANDEX_GPT_MODEL_URI=gpt://<folder_ID>/yandexgpt-5.1
YANDEX_LITE_MODEL_URI=gpt://<folder_ID>/yandexgpt-5-lite
YANDEX_EMBED_DOC_URI=emb://<folder_ID>/text-embeddings-v2-doc/
YANDEX_EMBED_QUERY_URI=emb://<folder_ID>/text-embeddings-v2-query/
```

Official docs used for the integration:

- [Yandex AI Studio text generation models](https://aistudio.yandex.ru/docs/en/ai-studio/concepts/generation/models)
- [Text Generation API](https://aistudio.yandex.ru/docs/en/ai-studio/text-generation/api-ref/TextGeneration/completion)
- [Text embeddings](https://aistudio.yandex.ru/docs/en/ai-studio/concepts/embeddings)
- [SpeechKit STT](https://aistudio.yandex.ru/docs/en/speechkit/stt/)

## Local Run

Create a real `.env` when you want to override defaults:

```bash
cp .env.example .env
```

Start the full stack:

```bash
docker compose up --build
```

Open:

- Frontend: http://localhost:3000
- Backend OpenAPI: http://localhost:8000/docs
- RabbitMQ management: http://localhost:15672
- MinIO console: http://localhost:9001
- Prometheus: http://localhost:9090

The first registered user becomes `admin`. After that, regular self-registrations become `student`, meaning a self-training user who can create and edit only their own `self_training` tests. Exam users should be created as `examinee`; they can see and take only assigned exams and cannot create or edit tests.

Create demo data:

```bash
docker compose --profile demo run --rm seed
```

Demo credentials:

```text
admin@tuneai.dev / password123
teacher@tuneai.dev / password123
student@tuneai.dev / password123
examinee@tuneai.dev / password123
```

## CORS

The browser client can call the backend only from origins listed in `CORS_ORIGINS`.

For local development the default value allows common frontend ports:

```env
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173
```

For a university or company website, set the exact site origins:

```env
CORS_ORIGINS=https://exam.example.edu,https://hr.example.com
NEXT_PUBLIC_API_BASE_URL=https://api.example.edu
```

`CORS_ORIGINS` also accepts a JSON array. Use `CORS_ORIGIN_REGEX` only for controlled subdomain patterns, for example preview deployments. Avoid `*` in production.

## Run Tests

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

The tests use SQLite, local uploads, and mock Yandex clients.

## Important Security Choices

- Yandex API keys are read only by backend/worker from environment variables.
- The browser only talks to TuneAI backend APIs.
- Passwords are hashed with bcrypt.
- JWTs are split into access and refresh token types.
- All object access checks are explicit: users cannot read other users' attempts.
- Uploads are constrained by content type and size.
- Tokens, passwords, and API keys are not logged.
- Auth endpoints have a simple in-memory rate limiter for MVP.
- Production deployments should terminate HTTPS at a reverse proxy and set stricter CORS origins.

## MVP Limitations

- The frontend is intentionally minimal and uses polling for processing status.
- RAG embeddings are stored as JSON for test portability; the Docker database uses a pgvector-ready image so this can be moved to native vector indexes later.
- Audio storage defaults to a shared local volume. S3/MinIO support is wired in the storage layer, but the slim Docker MVP does not install `boto3` by default; add `boto3`/`botocore` before setting `STORAGE_BACKEND=s3`.
- The SpeechKit async response parser is defensive because response nesting may vary across API versions; keep the exact request body aligned with the current official SpeechKit docs before production use.
