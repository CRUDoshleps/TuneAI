<div align="center">
  <img src="docs/screenshots/landing.png" alt="Главная страница TuneAI" width="860" />

  <h1>TuneAI</h1>

  <p><strong>Self-host платформа для тестов, интервью и самопроверки с голосовыми и текстовыми ответами.</strong></p>

  <p>
    <img alt="Next.js" src="https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white" />
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" />
    <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" />
    <img alt="RabbitMQ" src="https://img.shields.io/badge/RabbitMQ-FF6600?style=flat-square&logo=rabbitmq&logoColor=white" />
    <img alt="Docker" src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" />
    <img alt="Yandex AI Studio" src="https://img.shields.io/badge/Yandex%20AI%20Studio-FFCC00?style=flat-square" />
  </p>

  <p>
    <a href="#быстрый-запуск">Быстрый запуск</a> ·
    <a href="#публичная-demo-витрина">Demo-витрина</a> ·
    <a href="#кому-подходит">Кому подходит</a> ·
    <a href="#что-можно-настроить">Настройка</a> ·
    <a href="#как-устроена-проверка">Проверка</a> ·
    <a href="#документация">Документация</a>
  </p>
</div>

---

TuneAI помогает провести assessment: тест, устный экзамен, интервью или тренировку по материалам курса. Пользователь отвечает голосом или текстом. Система расшифровывает аудио, подбирает релевантные материалы через RAG, оценивает ответ по критериям и показывает результат. Преподаватель или администратор может назначать тесты людям и группам, проверять спорные ответы вручную и менять внешний вид инстанса под свою организацию.

## Быстрый запуск

```bash
scripts/init-self-host.sh
docker compose up --build -d
docker compose --profile demo run --rm seed
```

Откройте [http://localhost:3000](http://localhost:3000).

Публичная витрина возможностей доступна отдельно: [http://localhost:3000/demo](http://localhost:3000/demo).

Демо-аккаунты:

```text
student@tuneai.dev / password123
examinee@tuneai.dev / password123
candidate@tuneai.dev / password123
methodist@tuneai.dev / password123
teacher@tuneai.dev / password123
interviewer@tuneai.dev / password123
admin@tuneai.dev / password123
```

После входа администратора откройте раздел **Админка**, создайте пользователей или группу, затем назначьте опубликованный тест. Пользователь увидит только назначенные ему тесты.

Администратор может выдавать доступ тремя способами: создать пользователя вручную, импортировать CSV `email,full_name,role,password` или создать invite-ссылку. Если пароль сгенерирован системой или сброшен администратором, пользователь обязан сменить его после входа.

## Публичная demo-витрина

Страница `/demo` предназначена для внешнего сайта проекта и демонстрационного деплоя. Она показывает не локальную админку, а возможности TuneAI для посетителя: плагин Moodle, запуск у себя, встраиваемый виджет, RAG-материалы, настройки AI-проверки, пробную оценку, роли, группы и CI-проверки.

Для публичного сайта можно поставить `NEXT_PUBLIC_TUNEAI_TEMPLATE=official`. Если переменная не задана, `/demo` все равно сохраняет официальный бренд TuneAI, а основной интерфейс остается нейтральным self-host шаблоном.

## Кому подходит

**Студент локально.** Можно поднять систему на своем компьютере, создать тренировку, загрузить материалы и проверить себя.

**Школа, курс или команда.** Один инстанс обслуживает организацию: администратор создает аккаунты, группы, тесты, RAG-материалы и назначения.

**Оператор нескольких клиентов.** Каждый клиент может получить отдельный инстанс, бренд, домен, `.env` и набор пользователей. Так проще изолировать данные и настройки.

**Встраивание в сайт.** Внешний портал может открыть страницу `/widget` в iframe. Пользователь входит прямо в виджете и проходит назначенный тест без копирования frontend-логики TuneAI.

## Возможности

- тесты, интервью, экзамены и тренировки через единую сущность assessment;
- роли: студент, экзаменуемый, кандидат, методист, преподаватель, интервьюер, администратор;
- создание пользователей в админке и выдача логина с паролем;
- группы и назначение теста сразу группе;
- скрытие будущих вопросов до ответа на текущий;
- ответы голосом, текстом или любым из двух способов на уровне каждого вопроса;
- развёрнутые вопросы, одиночный и множественный выбор в одном assessment;
- создание черновика опроса из PPTX/PDF с выбором слайдов и проверкой предложенных вопросов;
- RAG-материалы на уровне организации, курса, теста или вопроса;
- генерация вопросов из RAG-материалов с кэшем похожих вопросов;
- AI-скиллы оценивания: сценарий, строгость, шкала, рубрика, политика материалов и инструкции;
- calibration preview перед публикацией теста;
- редактирование, копирование, удаление и изменение порядка вопросов;
- audit log, CSV-экспорт результатов и повторный запуск ошибок обработки в админке;
- очередь обработки через RabbitMQ и transactional outbox;
- mock-режим для локальной разработки без расходов на внешние модели.

## Как устроена проверка

1. Пользователь начинает попытку.
2. API возвращает только доступные вопросы.
3. Пользователь отправляет текст или аудиофайл, если такой режим разрешен вопросом.
4. Backend сохраняет ответ и событие в outbox.
5. Worker обрабатывает ответ: распознает аудио, получает RAG-контекст, применяет критерии и AI-скиллы.
6. Результат сохраняется в попытке.
7. Ответ с низкой уверенностью или спорным выводом попадает в очередь ручной проверки.

![Разбор ответа и итог преподавателя](docs/screenshots/student-result.png)

## Что можно настроить

Основные параметры лежат в `.env`.

```env
NEXT_PUBLIC_TUNEAI_TEMPLATE=unconfigured
NEXT_PUBLIC_TUNEAI_PRODUCT_NAME=My Exams
NEXT_PUBLIC_TUNEAI_LOGO_TEXT=ME
NEXT_PUBLIC_TUNEAI_LOGO_URL=https://example.com/logo.png
NEXT_PUBLIC_TUNEAI_ACCENT_COLOR=#ffcc13
NEXT_PUBLIC_TUNEAI_SURFACE_COLOR=#fffdf4
NEXT_PUBLIC_TUNEAI_PANEL_COLOR=#ffffff
NEXT_PUBLIC_TUNEAI_TEXT_COLOR=#111111
NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL=help@example.com
TEST_CREATOR_ROLES=teacher,interviewer,admin
ANSWER_REVIEWER_ROLES=teacher,admin
```

Для полной настройки публичного интерфейса используйте `NEXT_PUBLIC_TUNEAI_CONFIG_JSON`. Через него можно заменить тексты, ссылки, демо-сценарии, роли, видимость разделов, pipeline и список включенных модулей.

После изменения `NEXT_PUBLIC_*` переменных пересоберите frontend:

```bash
docker compose build frontend
docker compose up -d
```

Секреты Yandex AI Studio, базы данных, RabbitMQ, S3/MinIO и service-интеграций остаются только на backend и worker. Не передавайте их во frontend.

## Yandex AI Studio

По умолчанию проект работает в mock-режиме. Для реальных моделей заполните `.env`:

```env
YANDEX_MOCK=false
YANDEX_FOLDER_ID=<folder-id>
YANDEX_API_KEY=<api-key>
```

После запуска администратор может управлять AI-профилями в админке. Методисты и преподаватели настраивают поведение проверки через AI-скиллы.

## Архитектура

```text
frontend -> backend -> RabbitMQ -> worker -> AI provider
                  |          |
              PostgreSQL   MinIO
```

Стек: Next.js, FastAPI, PostgreSQL, RabbitMQ, MinIO, Docker Compose. Для локальной разработки можно использовать mock AI. Для self-host production заполните реальные credentials; публичный demo bootstrap либо отключите, либо ограничьте часовым лимитом и коротким TTL. Официальный deployment использует IAM-токен сервисного аккаунта VM вместо статического Yandex API key.

## Проверка

Backend:

```bash
cd backend
pip install -r requirements-dev.txt
pytest
alembic upgrade head
```

Frontend:

```bash
cd frontend
npm ci
npm test
npm run lint
npm run build
```

Self-host конфигурация:

```bash
scripts/init-self-host.sh
docker compose config
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

Эти проверки добавлены в GitHub Actions CI.

## Moodle локально

```bash
scripts/init-self-host.sh
docker compose -f docker-compose.yml -f docker-compose.moodle.local.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.moodle.local.yml exec moodle php /var/www/html/admin/cli/upgrade.php --non-interactive --allow-unstable
```

Moodle откроется на `http://localhost:18080`, логин `admin`, пароль из `MOODLE_ADMIN_PASSWORD` или `moodle-admin-password`. Плагин установлен как `local/tuneai`; mapping настраивается в `/local/tuneai/manage.php?courseid=<course-id>`.

## Backup

```bash
scripts/backup.sh
scripts/restore.sh backups/tuneai-YYYYMMDD-HHMMSS
```

Backup сохраняет PostgreSQL dump и uploads/material files. Для production добавьте cron или systemd timer вокруг `scripts/backup.sh`.

## Документация

- [Self-host развертывание](docs/self-host.md)
- [Интеграция во внешние сайты и widget](docs/site-integration.md)
- [API для интеграций](docs/api.md)
- [Роли и права](docs/roles.md)
- [RAG-материалы](docs/rag.md)
- [AI-скиллы](docs/ai-skills.md)
- [AI-провайдеры](docs/ai-providers.md)
- [AI Safety](docs/ai-safety.md)
- [Moodle-интеграция](docs/moodle.md)
- [Демо-сценарии](docs/demo.md)
- [Roadmap](docs/roadmap.md)

## Production deployment

Merge в `main` запускает полный CI, публикует immutable backend/frontend images
в Yandex Container Registry и автоматически обновляет
[tuneai.vnshk.ru](https://tuneai.vnshk.ru). GitHub аутентифицируется через
OIDC без постоянного ключа; VM проверяет health и точный git SHA, а при ошибке
возвращает предыдущие images. Схема и эксплуатационные команды описаны в
[production deployment guide](docs/production-deployment.md).

## Лицензия

Проект распространяется под MIT License. Подробнее см. [LICENSE](LICENSE).
