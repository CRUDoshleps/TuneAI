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
- `submission_service`: сбор payload и отправка ответа в TuneAI.
- Capabilities для управления mapping, отправки ответов и просмотра результатов.

## Следующий шаг

Нужно добавить Moodle UI:

- форму настройки mapping в activity;
- кнопку или observer для отправки ответа после завершения попытки;
- scheduled task для polling результата;
- запись оценки и feedback в Gradebook.
