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

Для владельца попытки в `questions` попадают только уже открытые вопросы. Это защищает следующие вопросы экзамена или интервью от утечки через API результата. Преподаватель, методист, интервьюер и администратор видят полную попытку в пределах своих прав.

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

Повторная отправка ответа с тем же `Idempotency-Key` возвращает уже созданный answer/result, а не создает дубль. Если ответ на этот вопрос уже есть, но ключ другой или отсутствует, API возвращает конфликт.

Аудио- и текстовые ответы ставятся в outbox и обрабатываются worker-процессом. HTTP-запрос быстро возвращает текущее состояние попытки, а финальная оценка появляется после обработки фоновой задачей.

## Публичная конфигурация

```text
GET /public/config
```

Возвращает runtime-конфигурацию frontend для брендинга и демо-сценариев.

## AI Providers

```text
GET /admin/ai-providers
POST /admin/ai-providers
PATCH /admin/ai-providers/{provider_id}
POST /admin/ai-providers/{provider_id}/activate
DELETE /admin/ai-providers/{provider_id}
```

Endpoints доступны только администратору. Секреты принимаются в `credentials`, но в read-ответах возвращаются только как `credentials_masked`. Поддерживаются провайдеры `mock`, `yandex`, `openai_compatible` и `local`.

## AI Skills

```text
GET /skills
POST /skills
POST /skills/upload
PATCH /skills/{skill_id}
DELETE /skills/{skill_id}
```

Endpoints доступны ролям, которые могут создавать тесты. Методист или преподаватель создает скилл, а затем привязывает его к тесту через `criteria.skill_ids`.

## Moodle

```text
GET /integrations/moodle/manifest
POST /integrations/moodle/submissions/text
POST /integrations/moodle/submissions/audio
GET /integrations/moodle/submissions/{external_submission_id}/result
```

Endpoints защищены `X-TuneAI-Integration-Key` и используются Moodle-плагином для выбора опубликованных тестов/вопросов, отправки текстовых или голосовых ответов, получения оценки и сигнала преподавателю `teacher_signal`.

`/manifest` поддерживает query params `methodist_email` и `test_id`. Submission payload может передавать `moodle_course_id`, `moodle_activity_id`, `moodle_group_id`, `moodle_group_name` и `methodist_email`. Если `methodist_email` указан, TuneAI проверяет, что тест принадлежит этому владельцу.

## Demo Bootstrap

```text
POST /public/demo/bootstrap
```

Работает только при `DEMO_BOOTSTRAP_ENABLED=true`. В production этот режим нужно отключать.

Демо-пользователи и демо-тесты создаются с TTL. Backend чистит истекшие демо-данные при новом bootstrap-запросе и ограничивает количество новых демо-пользователей в час.
