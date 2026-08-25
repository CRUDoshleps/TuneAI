# Demo

В TuneAI есть два демо-сценария: публичная демонстрация на сайте и заранее подготовленные seed-аккаунты.

## Публичное демо

Откройте сайт и выберите вкладку **Демонстрация**. Пользователь может переключаться между сценариями:

- самоподготовка;
- устный экзамен;
- интервью.

Кнопка **Демо-регистрация** вызывает `/public/demo/bootstrap`. Backend создает временного пользователя с подходящей ролью, тест под выбранный сценарий, RAG-материал и назначение теста, если сценарий закрытый.

Демо-пользователи и демо-тесты создаются с ограниченным сроком жизни. При новых bootstrap-запросах backend удаляет истекшие демо-данные и применяет лимит на количество новых демо-пользователей в час.

Настройки:

```env
DEMO_BOOTSTRAP_ENABLED=true
DEMO_BOOTSTRAP_LIMIT_PER_HOUR=30
DEMO_BOOTSTRAP_TTL_HOURS=24
```

Для production-стенда публичный bootstrap лучше отключать через `DEMO_BOOTSTRAP_ENABLED=false`.

## Seed-аккаунты

Запуск:

```bash
docker compose --profile demo run --rm seed
```

Аккаунты для локальной seed-базы:

```text
student@tuneai.dev / password123
examinee@tuneai.dev / password123
candidate@tuneai.dev / password123
methodist@tuneai.dev / password123
teacher@tuneai.dev / password123
interviewer@tuneai.dev / password123
admin@tuneai.dev / password123
```

Seed-аккаунты нужны для стабильных демонстрационных данных. Demo bootstrap подходит, когда нужен новый временный сценарий.

Админские аккаунты открываются через вкладку **Админка**. Обычные демо-пользователи входят через вкладку **Пользователь**.
