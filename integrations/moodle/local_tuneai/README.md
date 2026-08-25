# local_tuneai

Moodle local plugin для связи Moodle activity/question с TuneAI backend.

Текущая версия: `1.0.0`, `MATURITY_STABLE`, Moodle 4.0+.

Пользователь не вводит логин и пароль TuneAI. Moodle уже знает пользователя, поэтому плагин отправляет в TuneAI `moodle_user_id`, email, имя, course id, activity id и mapping на TuneAI test/question. TuneAI создает или находит связанного examinee, проверяет ответ и возвращает результат. Плагин сохраняет локальное зеркало результата и может записать оценку в Moodle Gradebook.

## Установка

Скопируйте каталог в Moodle:

```bash
cp -R integrations/moodle/local_tuneai /path/to/moodle/local/tuneai
```

Или соберите zip:

```bash
scripts/package-moodle-plugin.sh
```

Затем выполните upgrade:

```bash
php admin/cli/upgrade.php --non-interactive
```

## Настройки

В `Site administration -> Plugins -> Local plugins -> TuneAI integration` задайте:

- `Enable TuneAI`;
- `TuneAI base URL`;
- `TuneAI integration key`;
- `Moodle site identifier` — стабильное уникальное значение для этой установки;
- `Write grades to Moodle gradebook`;
- `Request timeout`.

На стороне TuneAI:

```env
MOODLE_INTEGRATION_ENABLED=true
MOODLE_INTEGRATION_TOKEN=<same-service-token>
MOODLE_INTEGRATION_SITE_ID=<same-stable-site-id>
MOODLE_INTEGRATION_OWNER_EMAILS=methodist@example.edu
```

Service token хранится только в Moodle backend и TuneAI backend. Браузер студента его не получает.

## Что делает плагин

- хранит mapping Moodle course/activity/question/group -> TuneAI test/question/methodist;
- читает пользователя из Moodle DB;
- отправляет текстовый или голосовой ответ в TuneAI service API;
- сохраняет `external_submission_id`, TuneAI attempt id, answer id, статус, score, grade, feedback и teacher signal;
- забирает готовый результат из TuneAI;
- записывает оценку в Moodle Gradebook через manual grade item;
- не публикует AI-оценку, пока `teacher_signal` требует ручной проверки;
- позволяет преподавателю проверить балл и feedback непосредственно в Moodle;
- поддерживает idempotent повторную отправку и отдельные попытки пересдачи;
- реализует Moodle Privacy API для экспорта и удаления локальных данных.

## Основные классы

- `client`: HTTP-клиент для `/integrations/moodle/*`.
- `mapping_repository`: mapping и локальное зеркало submission/result.
- `question_reader`: чтение текста из `question_attempts`.
- `submission_service`: сбор payload из Moodle identity, отправка ответа, polling результата.
- `gradebook_service`: запись проверенного результата в Moodle Gradebook.
- `task/sync_submissions`: scheduled polling pending submissions с backoff.
- `manage.php`: страница проверки соединения, manifest и mapping.
- `index.php`, `take.php`, `result.php`, `results.php`: страницы заданий, ответа, результата и сводки преподавателя.
- `upload_audio.php`: endpoint Moodle, который принимает запись из браузера и отправляет ее в TuneAI.
- `templates/recorder.mustache` и `amd/src/recorder.js`: простой recorder UI на MediaRecorder.

## Text flow

1. Учитель связывает Moodle question с TuneAI question.
2. Студент отвечает в Moodle.
3. Плагин берет ответ из Moodle question attempt.
4. Плагин отправляет payload в TuneAI:

```json
{
  "external_submission_id": "course-10-cm-7-qa-22-user-42",
  "external_attempt_id": "moodle-quba-1234-user-42",
  "moodle_user_id": "42",
  "moodle_course_id": "10",
  "moodle_activity_id": "7",
  "user_email": "student@example.edu",
  "user_full_name": "Moodle Student",
  "test_id": "<tuneai-test-id>",
  "question_id": "<tuneai-question-id>",
  "text": "Ответ из Moodle"
}
```

5. TuneAI возвращает queued status.
6. Scheduled task или ручной вызов `refresh_submission_result()` забирает готовый result.
7. Если ручная проверка не нужна, результат записывается в Moodle Gradebook.
8. При `review_recommended` преподаватель подтверждает итоговый балл в Moodle, после чего он публикуется в Gradebook.

## Voice flow

Для голосового ответа отрендерите recorder:

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

Браузер отправляет запись в Moodle, а Moodle backend пересылает файл в TuneAI. Audio upload ограничен 25 MB и принимает `webm`, `ogg`, `mpeg`, `mp4`, `wav`.

## Mapping

Mapping хранится в `local_tuneai_map`.

Откройте страницу:

```text
/local/tuneai/manage.php?courseid=<course-id>
```

На ней можно проверить соединение, отфильтровать manifest по email методиста или test id, увидеть `answer_mode` и сохранить mapping.

```php
$repository = new \local_tuneai\mapping_repository();
$repository->upsert_mapping(
    $courseid,
    $cmid,
    $moodlequestionid,
    $groupid,
    $tuneaitestid,
    $tuneaiquestionid,
    $methodistemail
);
```

Если `groupid` задан, mapping применяется только к группе. Если группового mapping нет, плагин использует общий mapping с внутренним `groupid = 0`.

## Gradebook

`gradebook_service` создает manual grade item:

```text
itemtype=manual
iteminstance=<cmid>
itemnumber=<stable hash TuneAI question id>
```

`finalgrade` равен `score`, а `grademax` равен `max_score`, который вернул TuneAI. Feedback сохраняется в grade feedback.

## Проверка

Из корня TuneAI:

```bash
tests/moodle/run-moodle-e2e.sh
```

Smoke поднимает TuneAI и Moodle в Docker, устанавливает плагин, создает mapping, отправляет ответ от Moodle-пользователя, проверяет пересдачу, блокировку provisional AI grade и публикацию оценки после ручной проверки.
