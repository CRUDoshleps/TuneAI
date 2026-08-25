# Интеграция с Moodle

TuneAI предоставляет service API и Moodle local plugin для связки Moodle activity/question с TuneAI assessment.

Moodle может:

- записывать устный ответ и отправлять аудио в TuneAI;
- брать уже введенный текстовый ответ из Moodle и отправлять его на проверку;
- получать результат проверки;
- выставлять оценку обратно в Moodle Gradebook;
- показывать преподавателю сигнал, если нужна ручная проверка.

![Локальный Moodle-контейнер](screenshots/moodle-local-login.png)

Пользователь не вводит логин и пароль TuneAI. Moodle уже знает участника курса, поэтому плагин отправляет в TuneAI Moodle identity: `moodle_user_id`, email, имя, course id, activity id и mapping на TuneAI test/question.

Плагин лежит в [integrations/moodle/local_tuneai](../integrations/moodle/local_tuneai). Его можно положить в чужой Moodle как `local/tuneai`.

## Включение

```env
MOODLE_INTEGRATION_ENABLED=true
MOODLE_INTEGRATION_TOKEN=<shared-service-token>
MOODLE_INTEGRATION_SITE_ID=<stable-unique-moodle-site-id>
MOODLE_INTEGRATION_OWNER_EMAILS=methodist@example.edu
```

Каждый запрос должен передавать header:

```text
X-TuneAI-Integration-Key: <shared-service-token>
X-TuneAI-Moodle-Site: <stable-unique-moodle-site-id>
```

Service token хранится только на стороне Moodle или интеграционного backend. Не передавайте его в браузер студента.

![TuneAI API endpoints для Moodle](screenshots/moodle-swagger-endpoints.png)

## Установка плагина в Moodle

1. Скопируйте каталог `integrations/moodle/local_tuneai` в Moodle как `local/tuneai`.
2. Откройте админку Moodle и завершите установку local plugin.
3. В настройках `Site administration -> Plugins -> Local plugins -> TuneAI integration` укажите:
   - `Enable TuneAI`;
   - `TuneAI base URL`;
   - `TuneAI integration key`;
   - `Moodle site identifier`;
   - `Write grades to Moodle gradebook`;
   - `Request timeout`.
4. На стороне TuneAI включите:

```env
MOODLE_INTEGRATION_ENABLED=true
MOODLE_INTEGRATION_TOKEN=<same-service-token>
MOODLE_INTEGRATION_SITE_ID=<same-stable-site-id>
MOODLE_INTEGRATION_OWNER_EMAILS=methodist@example.edu
```

Плагин содержит:

- таблицу `local_tuneai_map` для mapping Moodle course/activity/question/group -> TuneAI test/question/methodist;
- таблицу `local_tuneai_submission` для зеркала статуса проверки;
- capabilities `local/tuneai:manage`, `local/tuneai:submit`, `local/tuneai:viewresults`;
- `client.php` для вызова TuneAI;
- `question_reader.php` для чтения Moodle `question_attempts`;
- `submission_service.php` для отправки текстового или голосового ответа в TuneAI и polling результата;
- `gradebook_service.php` для записи проверенного результата в Moodle Gradebook;
- `/local/tuneai/manage.php` для проверки соединения, чтения manifest и сохранения mapping;
- `/local/tuneai/index.php`, `take.php`, `result.php` и `results.php` для прохождения и просмотра результатов;
- scheduled task `local_tuneai\task\sync_submissions` для polling незавершенных submissions;
- `upload_audio.php`, `templates/recorder.mustache`, `amd/src/recorder.js` для записи голоса через браузер и безопасной отправки через Moodle backend.

## Связка Moodle и TuneAI

Минимальная модель данных на стороне Moodle:

- Moodle course id;
- Moodle activity id, например quiz, assignment или custom activity;
- Moodle question id или slot id;
- Moodle group id, если один и тот же вопрос в разных группах должен вести в разные TuneAI тесты (для общей связки хранится `0`);
- TuneAI `test_id`;
- TuneAI `question_id`;
- политика ручной проверки при `teacher_signal`.

Связку можно настроить на странице `/local/tuneai/manage.php?courseid=<course-id>`. Преподаватель проверяет соединение с backend, видит опубликованные TuneAI tests из manifest, выбирает question и сохраняет Moodle question id -> TuneAI question id. В таблице виден `answer_mode`: `audio`, `text` или `both`.

Перед настройкой mapping Moodle может запросить TuneAI manifest:

```text
GET /integrations/moodle/manifest?methodist_email=methodist@example.edu
```

Ответ содержит опубликованные тесты владельца и список вопросов. У каждого вопроса есть `answer_mode`: `audio`, `text` или `both`. Moodle UI должен показывать только разрешенный способ ответа.

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
  "moodle_group_id": "group-3",
  "moodle_group_name": "PI-101",
  "methodist_email": "methodist@example.edu",
  "user_email": "student@example.edu",
  "user_full_name": "Student Name",
  "test_id": "TuneAI test id",
  "question_id": "TuneAI question id",
  "text": "Student text answer from Moodle"
}
```

TuneAI создает или переиспользует пользователя Moodle как `examinee`, назначает опубликованный тест, создает попытку и ставит ответ в тот же outbox/worker pipeline, что и обычные ответы TuneAI.

`external_submission_id` работает как idempotency key. Повтор такого же запроса вернет существующий answer/result.

Если `methodist_email` указан, TuneAI проверяет, что `test_id` принадлежит этому владельцу. Если Moodle отправит вопрос в чужой тест, API вернет `403`.

Текстовый сценарий для Moodle:

1. Студент отправляет ответ в Moodle.
2. Moodle plugin получает текст из question attempt или assignment submission.
3. Plugin вызывает `/integrations/moodle/submissions/text`.
4. Moodle показывает студенту статус обработки.
5. Plugin опрашивает result endpoint, сохраняет feedback и при готовности пишет оценку в Gradebook.

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
- `moodle_group_id`;
- `moodle_group_name`;
- `methodist_email`;
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
4. Plugin отправляет файл в `local/tuneai/upload_audio.php`.
5. Moodle backend вызывает `/integrations/moodle/submissions/audio` с service token.
6. TuneAI сохраняет файл, ставит outbox job и возвращает текущее состояние submission.

Не отправляйте `X-TuneAI-Integration-Key` напрямую из браузера. Браузер должен общаться с Moodle backend, а Moodle backend уже вызывает TuneAI.
Endpoint принимает аудио до 25 MB в форматах `webm`, `ogg`, `mpeg`, `mp4`, `wav` и проверяет сигнатуру содержимого.

Recorder UI подключается так:

```php
echo $OUTPUT->render_from_template('local_tuneai/recorder', [
    'endpoint' => (new moodle_url('/local/tuneai/upload_audio.php'))->out(false),
    'courseid' => $course->id,
    'cmid' => $cm->id,
    'questionid' => $questionid,
    'groupid' => $groupid,
    'sesskey' => sesskey(),
]);
$PAGE->requires->js_call_amd('local_tuneai/recorder', 'init', ['.local-tuneai-recorder']);
```

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

Moodle выставляет `score/max_score` в Gradebook только при `result_ready=true` и `teacher_signal="none"`. AI-результат с другим сигналом сохраняется как provisional и показывается преподавателю, но не становится итоговой оценкой.

`local_tuneai` делает это через `submission_service::refresh_submission_result()`. Метод обновляет локальную запись `local_tuneai_submission` и, если включен `gradesync`, вызывает `gradebook_service`.

В production polling выполняет scheduled task `local_tuneai\task\sync_submissions`. Он выбирает pending submissions, повторяет запрос с backoff, сохраняет `last_error` и при готовом результате пишет оценку в Gradebook.

Пример логики:

```text
if result_ready=false:
  keep submission in processing state

if result_ready=true and teacher_signal=none:
  write grade and feedback to Gradebook

if result_ready=true and teacher_signal!=none:
  do not write grade
  mark submission for teacher review in Moodle
  show review_reason to teacher

if teacher approves score and feedback:
  send audited Moodle review to TuneAI
  write reviewed score to Gradebook
```

## Рекомендуемый flow

1. Преподаватель связывает Moodle activity/question с TuneAI `test_id` и `question_id`.
2. Студент надиктовывает ответ в Moodle или отправляет текст.
3. Moodle отправляет ответ в TuneAI со стабильным `external_submission_id`.
4. Moodle опрашивает result endpoint.
5. Moodle ставит сигнал преподавателю, если `review_required=true`.
6. Преподаватель подтверждает итоговый балл и feedback на странице результата.
7. Moodle записывает только финальную оценку в Gradebook.

TuneAI принимает submissions только для опубликованных тестов.

## Что уже делает Moodle plugin

- Хранит mapping по `courseid`, `cmid`, `questionid` и опциональному `groupid`.
- Берет пользователя из Moodle DB и не просит TuneAI credentials у студента.
- Показывает страницу mapping и проверку соединения с backend.
- Отправляет текстовые ответы через service API.
- Принимает голосовую запись в Moodle и пересылает файл в TuneAI с service token.
- Сохраняет локальное зеркало submission/result.
- Забирает готовый result и записывает score/feedback в Moodle Gradebook.
- Запускает scheduled polling pending submissions.
- Показывает задания студенту, сводку ответов преподавателю и форму ручной проверки.
- Экспортирует и удаляет локальные пользовательские данные через Moodle Privacy API.

## Ограничения интеграции

- Более удобное автоматическое чтение Moodle question id из конкретных activity.
- Mapping на стандартные Quiz/Assignment пока настраивается преподавателем через страницу плагина.

## E2E-проверка с Moodle в Docker

Для локальной проверки можно поднять TuneAI, worker, RabbitMQ, PostgreSQL и настоящий Moodle-контейнер:

```bash
tests/moodle/run-moodle-e2e.sh
```

Сценарий:

- поднимает отдельный compose project `tuneai-moodle-e2e`;
- включает mock AI и Moodle integration token только для этого прогона;
- ждет готовности backend и Moodle;
- устанавливает `local_tuneai` через Moodle upgrade;
- запускает PHP smoke-тест внутри Moodle-контейнера;
- создает demo exam в TuneAI;
- создает Moodle course/user и mapping;
- отправляет текстовый Moodle submission через классы plugin;
- проверяет idempotency повтора;
- проверяет отдельную попытку пересдачи;
- дожидается результата через scheduled task plugin;
- валидирует `score`, `max_score`, `grade`, `feedback`, `confidence` и `teacher_signal`;
- проверяет, что provisional AI score не попал в журнал;
- выполняет ручную проверку и затем проверяет запись оценки в `grade_items` и `grade_grades`.

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

Успешный smoke подтверждает, что Moodle-контейнер установил plugin, передал identity Moodle-пользователя в TuneAI, получил idempotent replay, дождался результата worker pipeline и записал оценку в Moodle Gradebook.

CI также собирает Moodle plugin archive:

```bash
scripts/package-moodle-plugin.sh
```

Artifact называется `local_tuneai.zip`.
