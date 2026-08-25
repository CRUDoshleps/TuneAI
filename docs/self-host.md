# Self-host развертывание

Эта страница для человека, который поднимает TuneAI локально или на сервере организации.

## Режимы использования

| Режим | Когда подходит | Что включить |
| --- | --- | --- |
| Локальная самопроверка | Один студент запускает систему для себя | `YANDEX_MOCK=true` или свои AI-ключи, seed-аккаунт или обычная регистрация |
| Один курс или школа | Есть администратор, группы и назначенные тесты | Админка, группы, назначения, RAG-библиотека, widget при необходимости |
| Несколько клиентов | Нужно обслуживать разные школы или команды | Отдельный инстанс, домен, `.env`, база и storage на каждого клиента |

Для нескольких клиентов лучше не смешивать данные в одной базе. Проще сопровождать отдельные инстансы: один клиент, один домен, одна конфигурация.

## Локальный запуск

```bash
scripts/init-self-host.sh
docker compose up --build -d
docker compose --profile demo run --rm seed
```

Откройте `http://localhost:3000`.

Проверьте, что контейнеры запущены:

```bash
docker compose ps
```

## Что сделать после запуска

1. Войдите под `admin@tuneai.dev / password123`, если использовали seed.
2. Откройте **Админка**.
3. Создайте пользователей или группу.
4. Откройте **Конструктор** и создайте assessment.
5. Добавьте вопросы. Для каждого вопроса выберите формат ответа: голос, текст или оба варианта.
6. Загрузите материалы в **Настройка** или в блок RAG конструктора.
7. Настройте AI-скилл и выполните calibration preview.
8. Опубликуйте тест и назначьте его пользователю или группе.

Пользователь увидит только опубликованные тесты, которые назначены ему напрямую или через группу.

## Выдача доступа

В админке есть три рабочих способа:

- ручное создание пользователя с заданным паролем;
- импорт CSV с колонками `email,full_name,role,password`;
- invite-ссылка, которую можно отправить человеку через почту или мессенджер.

Если пароль сгенерирован системой или сброшен администратором, аккаунт получает флаг `must_change_password`. До смены пароля backend разрешает только `/auth/me` и `/auth/change-password`.

Для сброса пароля откройте **Админка -> Пользователи** и нажмите **Сброс**. Временный пароль показывается один раз.

## Настройка бренда

Frontend получает публичную конфигурацию через:

```text
GET /public/config
```

Основные переменные:

| Переменная | Для чего нужна |
| --- | --- |
| `NEXT_PUBLIC_TUNEAI_TEMPLATE` | `unconfigured` для нейтрального self-host шаблона или `official` для официальной презентации |
| `NEXT_PUBLIC_TUNEAI_PRODUCT_NAME` | Название в интерфейсе |
| `NEXT_PUBLIC_TUNEAI_LOGO_TEXT` | Текстовый логотип, если нет картинки |
| `NEXT_PUBLIC_TUNEAI_LOGO_URL` | URL логотипа |
| `NEXT_PUBLIC_TUNEAI_ACCENT_COLOR` | Основной акцентный цвет |
| `NEXT_PUBLIC_TUNEAI_SURFACE_COLOR` | Цвет фона страницы |
| `NEXT_PUBLIC_TUNEAI_PANEL_COLOR` | Цвет панелей |
| `NEXT_PUBLIC_TUNEAI_TEXT_COLOR` | Основной цвет текста |
| `NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL` | Контакт для помощи пользователям |
| `NEXT_PUBLIC_TUNEAI_CONFIG_JSON` | Полная JSON-конфигурация текстов, ролей, сценариев и видимости разделов |

Пример:

```env
NEXT_PUBLIC_TUNEAI_TEMPLATE=unconfigured
NEXT_PUBLIC_TUNEAI_PRODUCT_NAME=Faculty Exams
NEXT_PUBLIC_TUNEAI_LOGO_TEXT=FE
NEXT_PUBLIC_TUNEAI_LOGO_URL=https://school.example.edu/logo.svg
NEXT_PUBLIC_TUNEAI_ACCENT_COLOR=#ffcc13
NEXT_PUBLIC_TUNEAI_SURFACE_COLOR=#fffdf4
NEXT_PUBLIC_TUNEAI_PANEL_COLOR=#ffffff
NEXT_PUBLIC_TUNEAI_TEXT_COLOR=#111111
NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL=help@school.example.edu
```

После изменения `NEXT_PUBLIC_*` переменных пересоберите frontend:

```bash
docker compose build frontend
docker compose up -d
```

## Настройка ролей

```env
TEST_CREATOR_ROLES=student,methodist,teacher,interviewer,admin
ANSWER_REVIEWER_ROLES=teacher,interviewer,admin
```

`TEST_CREATOR_ROLES` определяет, кто может создавать тесты, вопросы, материалы и AI-скиллы.

`ANSWER_REVIEWER_ROLES` определяет, кто может видеть очередь ручной проверки и менять итоговый балл.

## AI и секреты

Для локальной разработки можно оставить mock:

```env
YANDEX_MOCK=true
```

Для реальных моделей:

```env
YANDEX_MOCK=false
YANDEX_FOLDER_ID=<folder-id>
YANDEX_API_KEY=<api-key>
```

API-ключи должны быть только у backend и worker. Не используйте префикс `NEXT_PUBLIC_` для секретов.

## Widget на внешнем сайте

Если у школы уже есть свой сайт или кабинет, не нужно копировать UI TuneAI. Поднимите TuneAI на отдельном домене и встроите:

```html
<iframe
  src="https://tuneai.example.edu/widget?test_id=<optional-test-id>"
  title="Assessment"
  allow="microphone"
  style="width: 100%; min-height: 760px; border: 0;"
></iframe>
```

Добавьте домен внешнего сайта:

```env
CORS_ORIGINS=https://school.example.edu
EMBED_ALLOWED_ORIGINS=https://school.example.edu
NEXT_PUBLIC_TUNEAI_EMBED_ALLOWED_ORIGINS=https://school.example.edu
```

Подробнее: [Интеграция во внешние сайты и widget](site-integration.md).

## Production настройки

Минимальный набор:

```env
APP_ENV=production
PUBLIC_ORIGIN=https://tuneai.example.edu
TUNEAI_DOMAIN=tuneai.example.edu
POSTGRES_PASSWORD=<random>
RABBITMQ_PASSWORD=<random>
MINIO_ROOT_PASSWORD=<random>
DEMO_BOOTSTRAP_ENABLED=false
YANDEX_MOCK=false
YANDEX_FOLDER_ID=<folder-id>
YANDEX_API_KEY=<api-key>
```

Проверьте перед запуском:

- `SECRET_KEY` задан и не используется в другом окружении;
- `DATABASE_URL` указывает на production PostgreSQL;
- `RABBITMQ_URL` доступен backend и worker;
- `S3_*` или MinIO настроены для хранения аудио и файлов;
- `CORS_ORIGINS` содержит только доверенные домены;
- `EMBED_ALLOWED_ORIGINS` содержит только сайты, где разрешен iframe.

Запуск production override:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

В этом режиме наружу открыты только `80/443` у Caddy. Postgres, RabbitMQ, MinIO, backend и frontend остаются внутри Docker-сети.

## Health dashboard

Откройте **Админка -> Система**. Backend проверяет:

- API и авторизацию;
- PostgreSQL;
- outbox/worker состояние;
- RabbitMQ socket;
- uploads storage;
- AI provider или mock mode;
- Moodle service API;
- последнюю ошибку обработки.

Эти данные также доступны через `GET /admin/system` для администратора.

## Backup и restore

```bash
scripts/backup.sh
scripts/restore.sh backups/tuneai-YYYYMMDD-HHMMSS
```

Backup сохраняет:

- `postgres.dump`: база TuneAI;
- `uploads.tar.gz`: аудио, материалы и локальные файлы.

Пример cron:

```cron
15 2 * * * cd /srv/tuneai && BACKUP_DIR=/srv/tuneai-backups scripts/backup.sh
```

После restore запустите:

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
```

Проверьте `/admin/system` и одну старую попытку с результатом.

## Moodle quick start

```bash
scripts/init-self-host.sh
docker compose -f docker-compose.yml -f docker-compose.moodle.local.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.moodle.local.yml exec moodle php /var/www/html/admin/cli/upgrade.php --non-interactive --allow-unstable
```

Moodle доступен на `http://localhost:18080`.

Данные по умолчанию:

```text
admin / moodle-admin-password
```

В Moodle откройте `Site administration -> Plugins -> Local plugins -> TuneAI integration`, укажите backend URL и `MOODLE_INTEGRATION_TOKEN`. Mapping настраивается на странице `/local/tuneai/manage.php?courseid=<course-id>`.

## Проверка перед обновлением

```bash
cd backend
pytest
alembic upgrade head
```

```bash
cd frontend
npm test
npm run lint
npm run build
```

```bash
docker compose config
```
