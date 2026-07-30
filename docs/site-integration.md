# Интеграция TuneAI во внешние сайты

TuneAI можно подключать к внешнему сайту двумя способами:

- встроить уже поднятый frontend как отдельную страницу или iframe;
- отправлять ответы через API из своего backend или frontend-клиента.

В текущем коде нет отдельного JavaScript SDK для виджета. Поэтому безопасный production-вариант сейчас - держать авторизацию и служебные ключи на backend внешней платформы, а в браузере оставлять только пользовательский токен и `Idempotency-Key`.

![Главная страница TuneAI](screenshots/site-integration-home.png)

## Быстрый локальный запуск

```bash
cp .env.example .env
docker compose up --build -d
docker compose --profile demo run --rm seed
```

Открывайте frontend как `http://localhost:3000`. В Next.js dev-режиме адрес `127.0.0.1` может блокировать служебные dev-ресурсы, из-за чего клики по демо-кнопкам работают некорректно.

![Выбор демо-сценария](screenshots/site-integration-demo.png)

## Встраивание страницы

Этот вариант подходит, если внешнему сайту нужно быстро показать прохождение теста, но не хочется копировать frontend-логику TuneAI.

1. Поднимите TuneAI на отдельном домене, например `https://tuneai.example.edu`.
2. Настройте бренд и сценарии через `NEXT_PUBLIC_TUNEAI_CONFIG_JSON`.
3. Добавьте домен внешней платформы в `CORS_ORIGINS`.
4. На внешнем сайте откройте ссылку на нужный контур TuneAI или встроите страницу через iframe.

```html
<iframe
  src="https://tuneai.example.edu"
  title="TuneAI oral exam"
  allow="microphone"
  style="width: 100%; min-height: 760px; border: 0;"
></iframe>
```

Для записи голосового ответа iframe должен получать разрешение `allow="microphone"`, а сайт должен работать по HTTPS. На localhost браузеры обычно разрешают микрофон без HTTPS.

![Прохождение демо-попытки](screenshots/site-integration-demo-runner.png)

## API-интеграция

Этот вариант подходит для HR-платформ, образовательных порталов и отдельных сайтов с экзаменами, где UI уже есть, а TuneAI нужен как сервис проверки.

### 1. Авторизация

Обычные пользователи регистрируются или входят через публичные endpoints:

```text
POST /auth/register
POST /auth/login
```

Администраторы используют отдельный контур:

```text
POST /auth/admin/login
```

Не смешивайте публичные аккаунты студентов, кандидатов и экзаменуемых с админкой.

### 2. Создание попытки

После выбора теста внешний клиент создает попытку:

```http
POST /attempts
Authorization: Bearer <user-access-token>
Content-Type: application/json

{
  "test_id": "test-id"
}
```

Ответ содержит `attempt_id`, доступные вопросы и текущий статус. Для студента или кандидата API не раскрывает будущие вопросы до того, как они станут доступны.

### 3. Отправка текстового ответа

```http
POST /attempts/{attempt_id}/questions/{question_id}/text
Authorization: Bearer <user-access-token>
Idempotency-Key: <client-generated-key>
Content-Type: application/json

{
  "text": "Ответ пользователя"
}
```

`Idempotency-Key` нужно генерировать на клиенте для каждой отправки. Если сеть оборвалась и запрос повторился с тем же ключом, backend вернет уже созданный answer/result, а не создаст дубль.

### 4. Отправка голосового ответа

```http
POST /attempts/{attempt_id}/questions/{question_id}/audio
Authorization: Bearer <user-access-token>
Idempotency-Key: <client-generated-key>
Content-Type: multipart/form-data

audio=<audio/webm | audio/ogg | audio/mpeg | audio/mp4 | audio/wav>
```

Frontend внешнего сайта должен запросить доступ к микрофону, записать файл и отправить его как `audio`. Для браузерной интеграции добавьте внешний домен в `CORS_ORIGINS`; backend уже разрешает headers `Authorization`, `Content-Type`, `Idempotency-Key`, `X-Request-ID`.

### 5. Получение результата

```http
GET /attempts/{attempt_id}/result
Authorization: Bearer <user-access-token>
```

Результат появляется после фоновой обработки worker. В ответе есть баллы, feedback, расшифровка, источники RAG, confidence, компетенции и сигнал ручной проверки.

## Рекомендованный UX внешнего сайта

1. Пользователь открывает страницу экзамена или интервью на вашей платформе.
2. Платформа показывает краткий контекст, правила и кнопку начала.
3. Backend вашей платформы создает или выбирает пользователя TuneAI и назначенный тест.
4. Frontend создает попытку и показывает первый доступный вопрос.
5. Пользователь выбирает режим ответа: голосом или текстом.
6. Frontend отправляет ответ с `Idempotency-Key` и сразу показывает статус обработки.
7. Страница периодически запрашивает `/attempts/{attempt_id}/result`.
8. После готовности показывает оценку, feedback и предупреждение, если нужна ручная проверка.

## Безопасность

- Не отдавайте в браузер Yandex API keys, service tokens Moodle, admin password и credentials внешних моделей.
- Для service-to-service интеграций используйте backend внешней платформы.
- Ограничивайте видимость тестов назначениями и ролями.
- Для production отключайте публичный demo bootstrap: `DEMO_BOOTSTRAP_ENABLED=false`.
- Добавляйте cleanup временных пользователей и тестов для демо-контуров.

## Что нужно для полноценного widget SDK

Отдельный widget SDK стоит делать следующим этапом. Минимальный контракт:

- npm-пакет или один JS bundle;
- `mount(container, config)` для встраивания;
- настройки темы, текста, бренда и сценария;
- callback-и `onReady`, `onAnswerSubmitted`, `onResult`, `onError`;
- поддержка text/audio answers;
- безопасная авторизация через короткоживущий token, выданный backend внешнего сайта.
