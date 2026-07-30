# local_tuneai

Заготовка Moodle local plugin для интеграции чужого Moodle с TuneAI.

## Установка

Скопируйте каталог в Moodle:

```bash
cp -R integrations/moodle/local_tuneai /path/to/moodle/local/tuneai
```

Затем откройте админку Moodle и завершите установку plugin.

## Настройки

В `Site administration -> Plugins -> Local plugins -> TuneAI integration` задайте:

- `TuneAI base URL`;
- `TuneAI integration key`;
- `Enable TuneAI`.

На стороне TuneAI должны быть включены:

```env
MOODLE_INTEGRATION_ENABLED=true
MOODLE_INTEGRATION_TOKEN=<same-service-token>
```

## Что уже есть

- `local_tuneai_map`: mapping Moodle course/activity/question/group -> TuneAI test/question/methodist.
- `local_tuneai_submission`: локальное зеркало TuneAI submission/result.
- `client`: вызовы `/integrations/moodle/manifest`, `/submissions/text`, `/submissions/{id}/result`.
- `question_reader`: чтение текста вопроса и ответа из `question_attempts`.
- `submission_service`: сбор payload и отправка текстового или голосового ответа в TuneAI.
- `upload_audio.php`: Moodle endpoint, который принимает запись из браузера и отправляет ее в TuneAI.
- `templates/recorder.mustache` и `amd/src/recorder.js`: базовый MediaRecorder UI.
- Capabilities для управления mapping, отправки ответов и просмотра результатов.

Audio upload ограничен 25 MB и принимает `webm`, `ogg`, `mpeg`, `mp4`, `wav`.

## Следующий шаг

Нужно добавить Moodle UI:

- форму настройки mapping в activity;
- кнопку или observer для отправки текстового ответа после завершения попытки;
- подключение recorder template там, где нужен устный ответ;
- scheduled task для polling результата;
- запись оценки и feedback в Gradebook.

## Подключение recorder UI

На странице Moodle activity после настройки mapping можно отрендерить шаблон:

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

Браузер отправляет запись только в Moodle. Service token TuneAI остается на backend Moodle.
