# Интеграция с Moodle

TuneAI предоставляет service API для Moodle-плагина или интеграционного скрипта на стороне Moodle.

Moodle может:

- записывать устный ответ и отправлять аудио в TuneAI;
- брать уже введенный текстовый ответ из Moodle и отправлять его на проверку;
- получать результат проверки;
- выставлять оценку обратно в Moodle Gradebook;
- показывать преподавателю сигнал, если нужна ручная проверка.

![Локальный Moodle-контейнер](screenshots/moodle-local-login.png)

В текущем коде реализована backend-интеграция и Docker smoke-тест на реальном Moodle-контейнере. Готового Moodle plugin UI в репозитории пока нет: его нужно собрать поверх endpoints ниже.

## Включение

```env
MOODLE_INTEGRATION_ENABLED=true
MOODLE_INTEGRATION_TOKEN=<shared-service-token>
```

Каждый запрос должен передавать header:

```text
X-TuneAI-Integration-Key: <shared-service-token>
```

Service token хранится только на стороне Moodle или интеграционного backend. Не передавайте его в браузер студента.

![TuneAI API endpoints для Moodle](screenshots/moodle-swagger-endpoints.png)

## Связка Moodle и TuneAI

Минимальная модель данных на стороне Moodle:

- Moodle course id;
- Moodle activity id, например quiz, assignment или custom activity;
- Moodle question id или slot id;
- TuneAI `test_id`;
- TuneAI `question_id`;
- правила выставления оценки в Gradebook;
- политика ручной проверки при `teacher_signal`.

Связку лучше хранить в настройках Moodle activity. Преподаватель выбирает опубликованный TuneAI test, затем сопоставляет каждый Moodle question с TuneAI question.

## Текстовый ответ

```text
POST /integrations/moodle/submissions/text
```

```json
{
  "external_submission_id": "quiz-7-attempt-12-question-3",
  "external_attempt_id": "quiz-7-attempt-12",
  "moodle_user_id": "42",
  "moodle_course_id": "course-10",
  "moodle_activity_id": "quiz-7",
  "user_email": "student@example.edu",
  "user_full_name": "Student Name",
  "test_id": "TuneAI test id",
  "question_id": "TuneAI question id",
  "text": "Student text answer from Moodle"
}
```

TuneAI создает или переиспользует пользователя Moodle как `examinee`, назначает опубликованный тест, создает попытку и ставит ответ в тот же outbox/worker pipeline, что и обычные ответы TuneAI.

`external_submission_id` работает как idempotency key. Повтор такого же запроса вернет существующий answer/result.

Текстовый сценарий для Moodle:

1. Студент отправляет ответ в Moodle.
2. Moodle plugin получает текст из question attempt или assignment submission.
3. Plugin вызывает `/integrations/moodle/submissions/text`.
4. Moodle показывает студенту статус обработки.
5. Plugin опрашивает result endpoint и сохраняет feedback.

## Голосовой ответ

```text
POST /integrations/moodle/submissions/audio
Content-Type: multipart/form-data
```

Поля:

- `external_submission_id`;
- `external_attempt_id`;
- `moodle_user_id`;
- `moodle_course_id`;
- `moodle_activity_id`;
- `user_email`;
- `user_full_name`;
- `test_id`;
- `question_id`;
- `file`.

Moodle-плагин должен запросить доступ к микрофону внутри Moodle, записать ответ и загрузить `audio/webm`, `audio/ogg`, `audio/mpeg`, `audio/mp4` или `audio/wav`.

Голосовой сценарий для Moodle:

1. В Moodle activity появляется кнопка записи ответа.
2. Browser запрашивает разрешение на микрофон.
3. Plugin записывает аудио через MediaRecorder.
4. Plugin отправляет файл на Moodle backend.
5. Moodle backend вызывает `/integrations/moodle/submissions/audio` с service token.
6. TuneAI сохраняет файл, ставит outbox job и возвращает текущее состояние submission.

Не отправляйте `X-TuneAI-Integration-Key` напрямую из браузера. Браузер должен общаться с Moodle backend, а Moodle backend уже вызывает TuneAI.

## Получение результата

```text
GET /integrations/moodle/submissions/{external_submission_id}/result
```

Поля ответа, которые нужны Moodle:

- `result_ready`: закончила ли TuneAI AI-проверку;
- `score`: баллы для выставления;
- `max_score`: максимум баллов;
- `grade`: нормализованная оценка от `0` до `1`;
- `feedback`: комментарий AI для Moodle;
- `review_required`: нужна ли ручная проверка преподавателем;
- `teacher_signal`: `none`, `review_recommended` или `processing_failed`;
- `review_reason`: причина сигнала для преподавателя;
- `confidence`: уверенность AI.

Moodle должен выставлять `grade` или `score/max_score` в Gradebook только при `result_ready=true`. Если `teacher_signal != "none"`, Moodle может сохранить AI-результат, но должен пометить работу для ручной проверки преподавателем.

Пример логики:

```text
if result_ready=false:
  keep submission in processing state

if result_ready=true and teacher_signal=none:
  write grade and feedback to Gradebook

if result_ready=true and teacher_signal!=none:
  write provisional grade
  mark submission for teacher review
  show review_reason to teacher
```

## Рекомендуемый flow

1. Преподаватель связывает Moodle activity/question с TuneAI `test_id` и `question_id`.
2. Студент надиктовывает ответ в Moodle или отправляет текст.
3. Moodle отправляет ответ в TuneAI со стабильным `external_submission_id`.
4. Moodle опрашивает result endpoint.
5. Moodle записывает оценку и feedback.
6. Moodle ставит сигнал преподавателю, если `review_required=true`.

TuneAI принимает submissions только для опубликованных тестов.

## Что должен делать Moodle plugin

- Страница настроек activity: выбрать TuneAI test и сопоставить вопросы.
- UI прохождения: показать текстовый ответ или кнопку записи голоса.
- Backend controller: принять submission от Moodle, вызвать TuneAI service API.
- Scheduled task: периодически опрашивать result endpoint.
- Gradebook adapter: выставить оценку, feedback и статус ручной проверки.
- Teacher view: показать `teacher_signal`, `review_reason`, confidence и AI feedback.

## E2E-проверка с Moodle в Docker

Для локальной проверки можно поднять TuneAI, worker, RabbitMQ, PostgreSQL и настоящий Moodle-контейнер:

```bash
tests/moodle/run-moodle-e2e.sh
```

Сценарий:

- поднимает отдельный compose project `tuneai-moodle-e2e`;
- включает mock AI и Moodle integration token только для этого прогона;
- ждет готовности backend и Moodle;
- запускает PHP smoke-тест внутри Moodle-контейнера;
- создает demo exam в TuneAI;
- отправляет текстовый Moodle submission;
- проверяет idempotency повтора;
- дожидается результата worker pipeline;
- валидирует `score`, `max_score`, `grade`, `feedback`, `confidence` и `teacher_signal`.

После успешного или неуспешного прогона runner удаляет контейнеры и volumes. Чтобы оставить окружение для ручной диагностики:

```bash
KEEP_MOODLE_E2E=1 tests/moodle/run-moodle-e2e.sh
```

Когда `KEEP_MOODLE_E2E=1`, Moodle остается доступен на [http://localhost:18080](http://localhost:18080). Демо-логин контейнера:

```text
admin / moodle-e2e-admin-password
```

После ручной проверки остановите окружение:

```bash
docker compose -p tuneai-moodle-e2e -f docker-compose.yml -f docker-compose.moodle.yml down -v
```

После первого успешного build можно ускорить повторный прогон:

```bash
MOODLE_E2E_SKIP_BUILD=1 tests/moodle/run-moodle-e2e.sh
```

Успешный smoke подтверждает, что Moodle-контейнер смог вызвать TuneAI, отправить текстовый ответ, получить idempotent replay и дождаться результата worker pipeline.
