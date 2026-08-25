# AI Providers

TuneAI поддерживает runtime-профили AI-провайдеров в админке.

Администратор открывает раздел **Админка -> AI-провайдеры и ключи** и может:

- добавить профиль Yandex AI Studio;
- добавить OpenAI-compatible gateway;
- добавить локальную модель через Ollama, LM Studio, vLLM или другой OpenAI-compatible `/v1` endpoint;
- включить mock-профиль для демонстрации без внешних моделей;
- заменить ключи без пересборки frontend и backend;
- активировать один рабочий профиль;
- отключить или удалить устаревший профиль.

## Безопасность

API чтения не возвращает секреты в открытом виде. В ответе есть только `credentials_masked`, например `yc••••-key`.

При обновлении профиля пустое поле секрета означает "оставить текущий ключ". Чтобы удалить конкретный секрет через API, нужно отправить `null` для этого ключа.

Активировать можно только включенный и валидный профиль.

## Yandex AI Studio

Для Yandex-профиля нужны:

- `folder_id`;
- `api_key` или `iam_token`.

Опционально можно переопределить:

- `gpt_model_uri`;
- `embed_doc_uri`;
- `embed_query_uri`;
- `completion_url`;
- `embedding_url`;
- SpeechKit endpoints.

Yandex-профиль поддерживает SpeechKit STT, YandexGPT, embeddings и RAG.

## OpenAI-Compatible

Для OpenAI-compatible профиля нужны:

- `api_key`;
- `base_url` или пара `chat_completion_url` + `embedding_url`.

Опционально можно указать:

- `evaluation_model`;
- `embedding_model`;
- `embedding_url`;
- `temperature`;
- `max_tokens`.

Такой профиль использует chat completions для оценки текстовых ответов и embeddings для RAG. Для голосовых ответов нужен Yandex SpeechKit из `.env` или отдельный Yandex-профиль.

## Local Models

Локальный профиль нужен, когда модель запущена рядом с TuneAI или в вашей инфраструктуре:

- Ollama: `http://localhost:11434/v1`;
- LM Studio: `http://localhost:1234/v1`;
- vLLM или llama.cpp server с OpenAI-compatible API.

Для локального профиля API key необязателен. Обязателен `base_url` или пара `chat_completion_url` + `embedding_url`.

Пример:

```text
Provider: Local model
Base URL: http://localhost:11434/v1
Chat/evaluation model: llama3.1
Embedding model: nomic-embed-text
```

Локальный профиль использует локальный chat endpoint для проверки ответов и локальные embeddings для RAG. Если нужно проверять голосовые ответы, оставьте SpeechKit-настройки Yandex в `.env`; текстовые ответы полностью проходят через локальную модель.

## Fallback

Если в базе нет активного AI-профиля, TuneAI использует `.env`-настройки:

```env
YANDEX_MOCK=true
YANDEX_FOLDER_ID=<folder-id>
YANDEX_API_KEY=<api-key>
```

В production можно оставить `RUNTIME_AI_PROVIDER_CONFIG_ENABLED=true`, чтобы платформа стартовала без Yandex-ключей в окружении и ждала настройки активного профиля через админку.
