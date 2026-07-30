# Self-Host

TuneAI можно развернуть как настраиваемую self-host платформу.

## Локальный запуск

```bash
cp .env.example .env
docker compose up --build -d
docker compose --profile demo run --rm seed
```

Откройте `http://localhost:3000`.

## Настройка бренда

Frontend получает публичную конфигурацию через:

```text
GET /public/config
```

Основные переменные в `.env`:

```env
NEXT_PUBLIC_TUNEAI_TEMPLATE=unconfigured
NEXT_PUBLIC_TUNEAI_PRODUCT_NAME=Campus Oral AI
NEXT_PUBLIC_TUNEAI_LOGO_TEXT=CampusAI
NEXT_PUBLIC_TUNEAI_LOGO_URL=https://example.com/logo.png
NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL=help@example.com
NEXT_PUBLIC_TUNEAI_CONSULTATION_PERSON=Implementation Team
NEXT_PUBLIC_TUNEAI_CONFIG_JSON={}
```

Эта же схема конфигурации используется для официального демо-сайта и отдельных self-host установок.

## Production

Для production установите:

```env
APP_ENV=production
DEMO_BOOTSTRAP_ENABLED=false
YANDEX_MOCK=false
YANDEX_FOLDER_ID=<folder-id>
YANDEX_API_KEY=<api-key>
```

API-ключи должны оставаться только на backend и worker. Не передавайте их во frontend и не добавляйте в публичные переменные окружения.
