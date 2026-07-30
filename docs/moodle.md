# Moodle Integration

TuneAI предоставляет service API для Moodle-плагина или интеграционного скрипта на стороне Moodle.

Moodle может:

- записывать устный ответ и отправлять аудио в TuneAI;
- брать уже введенный текстовый ответ из Moodle и отправлять его на проверку;
- получать результат проверки;
- выставлять оценку обратно в Moodle Gradebook;
- показывать преподавателю сигнал, если нужна ручная проверка.

## Включение

```env
MOODLE_INTEGRATION_ENABLED=true
MOODLE_INTEGRATION_TOKEN=<shared-service-token>
```

Каждый запрос должен передавать header:

```text
X-TuneAI-Integration-Key: <shared-service-token>
```

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

## Рекомендуемый flow

1. Преподаватель связывает Moodle activity/question с TuneAI `test_id` и `question_id`.
2. Студент надиктовывает ответ в Moodle или отправляет текст.
3. Moodle отправляет ответ в TuneAI со стабильным `external_submission_id`.
4. Moodle опрашивает result endpoint.
5. Moodle записывает оценку и feedback.
6. Moodle ставит сигнал преподавателю, если `review_required=true`.

TuneAI принимает submissions только для опубликованных тестов.
