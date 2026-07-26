<div align="center">
  <img src="docs/screenshots/landing.png" alt="Главная страница TuneAI" width="860" />

  <h1>TuneAI</h1>

  <p><strong>Платформа устного тестирования с распознаванием речи, RAG и оценкой ответов через Yandex AI Studio.</strong></p>

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
    <a href="#возможности">Возможности</a> ·
    <a href="#сценарии">Сценарии</a> ·
    <a href="#архитектура">Архитектура</a> ·
    <a href="#проверка">Проверка</a>
  </p>
</div>

---

> Обычные тесты проверяют выбор правильного варианта. TuneAI проверяет устный ответ: как человек формулирует мысль, насколько полно раскрывает тему, где ошибается и какие материалы стоит повторить.

## Возможности

- устные ответы через микрофон;
- расшифровка речи через Yandex SpeechKit;
- поиск по учебным материалам через RAG;
- оценка ответа по критериям преподавателя;
- понятная обратная связь: ошибки, пропущенные пункты и рекомендации;
- роли студента, экзаменуемого, преподавателя и администратора;
- скрытие вопросов до начала попытки и последовательное открытие;
- очередь фоновой обработки через RabbitMQ и Transactional Outbox;
- безопасный mock-режим без расходов на API.

## Как это работает

1. Студент записывает ответ с микрофона.
2. Yandex SpeechKit превращает речь в текст.
3. Yandex Text Embeddings помогают найти релевантные фрагменты материалов для RAG.
4. YandexGPT проверяет ответ по критериям и формирует понятную обратную связь.
5. Спорные результаты отправляются преподавателю на ручную проверку.

![Разбор ответа и итог преподавателя](docs/screenshots/student-result.png)

## Технологии Яндекса

- **Yandex SpeechKit** — распознавание устной речи и получение текстовой расшифровки ответа.
- **Yandex Text Embeddings** — векторизация учебных материалов и запросов для RAG-поиска.
- **YandexGPT** — оценка ответа, поиск ошибок, пропущенных пунктов и генерация рекомендаций.
- **Yandex AI Studio** — единая платформа для подключения моделей Яндекса к приложению.

## Сценарии

**Самоподготовка.** Студент создает тренировку, загружает материалы, отвечает голосом и получает разбор слабых тем.

**Устный экзамен.** Экзаменуемый видит только назначенные тесты, вопросы открываются по одному, преподаватель получает отчет.

**Интервью.** Система задает вопросы кандидату, анализирует ответы и формирует структурированный итог для рекрутера.

## Быстрый запуск

```bash
cp .env.example .env
docker compose up --build -d
docker compose --profile demo run --rm seed
```

Откройте локально: [http://localhost:3000](http://localhost:3000)

Демо-аккаунты:

```text
student@tuneai.dev / password123
admin@tuneai.dev / password123
```

## Yandex AI Studio

По умолчанию проект запускается в mock-режиме. Чтобы включить реальные модели Яндекса, заполните `.env`:

```env
YANDEX_MOCK=false
YANDEX_FOLDER_ID=<folder-id>
YANDEX_API_KEY=<api-key>
```

Ключ используется только backend и worker. В браузер он не передается.

## Архитектура

```text
frontend -> backend -> RabbitMQ -> worker -> Yandex AI Studio
                  |          |
              PostgreSQL   MinIO
```

Основной стек: Next.js, FastAPI, PostgreSQL, RabbitMQ, MinIO и Docker Compose.

## Проверка

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Frontend собирается командой:

```bash
cd frontend
npm run build
```

## Лицензия

Исходный код доступен для ознакомления в рамках демонстрации проекта. Все права принадлежат CRUDoshleps. Подробнее см. [LICENSE](LICENSE).
