# CI/CD TuneAI в Yandex Cloud

Production pipeline описан в `.github/workflows/ci.yml` и запускается на каждый
push/merge в trunk-ветку `main`. Ручной повторный запуск доступен через
`workflow_dispatch`.

## Поток релиза

1. GitHub Actions запускает backend tests, Alembic upgrade на чистой БД,
   frontend lint/build/audit и проверку production Compose/shell scripts.
2. После успешных проверок job `release` собирает backend и frontend images с
   одним immutable тегом `sha-<40-hex-git-sha>` и выполняет smoke/secret scan.
3. GitHub OIDC token с audience `https://github.com/CRUDoshleps` обменивается
   на короткоживущий Yandex IAM token service account `tuneai-ci`.
4. CI публикует оба images в
   `cr.yandex/<registry-id>/tuneai/{backend,frontend}`. Production payload и SSH
   keys в GitHub не хранятся.
5. `tuneai-deploy.timer` на VM раз в минуту выбирает только последний git SHA,
   который присутствует одновременно в backend и frontend repositories.
6. Host получает application secrets из Lockbox своей instance identity,
   выполняет Alembic migrations и обновляет Compose stack. Backend и worker
   получают короткоживущий Yandex IAM-токен из metadata service аккаунта VM;
   статический Yandex API key для official production не используется.
7. Перед фиксацией релиза host выполняет embedding + completion deep probe,
   затем проверяет контейнеры и внешний `https://tuneai.vnshk.ru/api/health`
   с точным git SHA.
8. При ошибке приложение возвращается на предыдущий image tag. Миграции БД не
   откатываются, поэтому изменения схемы для обычного merge должны следовать
   expand/migrate/contract и оставаться совместимыми с предыдущей версией.
9. `tuneai-health.timer` раз в минуту проверяет внешний readiness с production
   PostgreSQL, AI readiness, точный deployed SHA, health контейнеров, rollout
   timer и заполнение системного диска.
10. После успешного rollout host сохраняет текущий и предыдущий TuneAI image для
   rollback, а более старые локальные TuneAI images удаляет. Registry хранит
   более длинную историю релизов по отдельной lifecycle policy.

## GitHub configuration

Repository variables:

| Variable | Назначение |
|---|---|
| `YC_REGISTRY_ID` | ID production Container Registry |
| `YC_SERVICE_ACCOUNT_ID` | ID service account `tuneai-ci` |
| `NEXT_PUBLIC_TUNEAI_TEMPLATE` | Публичный UI template |
| `NEXT_PUBLIC_TUNEAI_PRODUCT_NAME` | Публичное название продукта |
| `NEXT_PUBLIC_TUNEAI_*` | Остальная публичная branding-конфигурация при необходимости |

GitHub Secrets не требуются. Service account имеет только
`container-registry.images.pusher` на двух TuneAI repositories. Federation
credential ограничен subject:

```text
repo:CRUDoshleps/TuneAI:ref:refs/heads/main
```

Параметры WIF:

```text
issuer:   https://token.actions.githubusercontent.com
jwks-url: https://token.actions.githubusercontent.com/.well-known/jwks
audience: https://github.com/CRUDoshleps
```

Официальная документация: [Yandex Cloud WIF для GitHub](https://yandex.cloud/en/docs/iam/tutorials/wlif-github-integration)
и [Container Registry authentication](https://yandex.cloud/en/docs/container-registry/operations/authentication).

## VM configuration

`/srv/apps/tuneai/deploy/.env.production` содержит только runtime configuration
и resource IDs. В нём должны присутствовать:

```text
REGISTRY_IMAGE=cr.yandex/<registry-id>/tuneai
IMAGE_TAG=<текущий production tag>
LOCKBOX_SECRET_ID=<secret-id>
PUBLIC_HEALTH_URL=https://tuneai.vnshk.ru/api/health
```

Lockbox secret `tuneai-prod` содержит application secrets. Instance service
account `prod-runtime` имеет `lockbox.payloadViewer` только на этот secret и
`container-registry.images.puller` на production registry. Для AI runtime ему
также нужны folder roles `ai.languageModels.user` и `ai.speechkit-stt.user`.

Однократная установка watcher на уже подготовленной VM:

```bash
sudo /srv/apps/tuneai/deploy/install-cicd-host.sh
sudo systemctl start tuneai-deploy.service
```

## Диагностика и rollback

```bash
systemctl status tuneai-deploy.timer
systemctl status tuneai-health.timer
journalctl -u tuneai-health.service --since today
journalctl -u tuneai-deploy.service --since today
docker compose --project-name tuneai -f /srv/apps/tuneai/deploy/compose.yaml ps
curl -fsS https://tuneai.vnshk.ru/api/health | jq
curl -fsS https://tuneai.vnshk.ru/api/readiness | jq
curl -fsS https://tuneai.vnshk.ru/api/readiness/ai/deep | jq
```

Ручной rollback использует предыдущий immutable tag:

```bash
sudo /srv/apps/tuneai/deploy/deploy.sh sha-<previous-40-hex-git-sha>
```

Не удаляйте предыдущий рабочий image до успешного следующего rollout.
