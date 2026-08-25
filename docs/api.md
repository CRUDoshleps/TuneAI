# API

TuneAI предоставляет API для основного frontend, widget и внешних интеграций.

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

Вопросы в попытке содержат `answer_mode`.

| Значение | Разрешенный ответ |
| --- | --- |
| `audio` | Только аудио |
| `text` | Только текст |
| `both` | Аудио или текст |

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

Ответ на вопрос с одиночным или множественным выбором:

```text
POST /attempts/{attempt_id}/questions/{question_id}/choices
Header: Idempotency-Key: <client-generated-key>

{
  "selected_option_ids": ["stable-option-id"]
}
```

Закрытые вопросы проверяются детерминированно и не отправляются AI-провайдеру. `question_type` принимает `open_response`, `single_choice` или `multiple_choice`.

Если вопрос имеет `answer_mode=audio`, endpoint текстового ответа вернет `403` с `Text answers are disabled for this question`.

Если вопрос имеет `answer_mode=text`, endpoint аудиоответа вернет `403` с `Audio answers are disabled for this question`.

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

Скилл может задавать сценарий, язык, строгость, шкалу, порог ручной проверки, политику материалов, рубрику и дополнительные инструкции.

## Assessment Builder

```text
POST /tests
PATCH /tests/{test_id}
POST /tests/{test_id}/questions
PATCH /tests/{test_id}/questions/{question_id}
POST /tests/{test_id}/generate-questions
POST /tests/{test_id}/calibration-preview
POST /tests/{test_id}/assign
POST /tests/{test_id}/assign-group
```

`POST /tests/{test_id}/generate-questions` создает кандидатов вопросов из индексированных RAG-материалов. Ответ содержит вопросы, оценку новизны, фрагмент источника, расчетный token budget и признак reuse.

`POST /tests/{test_id}/calibration-preview` прогоняет выбранный AI-скилл на примерах ответов до публикации теста. Это помогает преподавателю увидеть, как модель оценит сильный, средний и слабый ответ.

## Импорт презентации

```text
POST /source-imports/upload?test_id={test_id}
GET /source-imports?test_id={test_id}
GET /source-imports/{source_id}
POST /source-imports/{source_id}/generate
POST /source-imports/{source_id}/candidates/{candidate_id}/accept
```

Upload принимает PPTX или PDF до 25 МБ. Ответ сохраняет границы слайдов/страниц и заметки докладчика. Генерация выполняется через outbox/worker; клиент опрашивает `GET /source-imports/{source_id}` до статуса `completed` или `failed`.

## Операционная админка

```text
GET /admin/audit-log
GET /admin/results/export.csv
POST /admin/failed-jobs/{job_id}/retry
```

CSV возвращается с UTF-8 BOM для корректного открытия кириллицы в Excel. Повторный запуск идемпотентен: если задача уже стоит в очереди, дубликат outbox-события не создаётся.

## Материалы

```text
GET /materials
POST /materials
POST /materials/upload
DELETE /materials/{material_id}
```

Материал может относиться к организации, курсу, тесту или вопросу. В проверку попадают только материалы со статусом `indexed`.

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
