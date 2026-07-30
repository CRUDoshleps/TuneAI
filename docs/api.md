# API

TuneAI предоставляет API приложения и стабильный контракт результата для интеграций.

## Авторизация

Публичные пользователи и администраторы используют разные точки входа.

```text
POST /auth/register
POST /auth/login
```

Обычная регистрация всегда создает аккаунт `student`. Публичный вход отклоняет админские аккаунты с ошибкой `Use admin login`.

```text
POST /auth/admin/register
POST /auth/admin/login
```

Админская регистрация доступна только для первого администратора. После этого endpoint возвращает `Admin registration is closed`; новых сотрудников должен создавать существующий администратор через users API. Админский вход принимает только админские аккаунты и отклоняет обычных пользователей с ошибкой `Admin account required`.

## Попытки

```text
POST /attempts
GET /attempts/{attempt_id}
GET /attempts/{attempt_id}/result
```

`/result` возвращает стабильную схему: статус ответа, расшифровку, балл, обратную связь, фрагменты источников, confidence и статус ручной проверки.

## Ответы

Аудиоответ:

```text
POST /attempts/{attempt_id}/questions/{question_id}/audio
Header: Idempotency-Key: <client-generated-key>
```

Текстовый ответ:

```text
POST /attempts/{attempt_id}/questions/{question_id}/text
Header: Idempotency-Key: <client-generated-key>

{
  "text": "Answer text"
}
```

Текстовые ответы пропускают SpeechKit и сразу идут в RAG-поиск и AI-оценку.

## Публичная конфигурация

```text
GET /public/config
```

Возвращает runtime-конфигурацию frontend для брендинга и демо-сценариев.

## Demo Bootstrap

```text
POST /public/demo/bootstrap
```

Работает только при `DEMO_BOOTSTRAP_ENABLED=true`. В production этот режим нужно отключать.
