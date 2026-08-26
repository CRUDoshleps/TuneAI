FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17

ARG APP_REVISION=development

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_COMPILE=1 \
    APP_REVISION=${APP_REVISION} \
    HOME=/home/tuneai

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl ffmpeg \
    && curl --fail --silent --show-error \
        https://storage.yandexcloud.net/cloud-certs/CA.pem \
        --output /usr/local/share/ca-certificates/YandexInternalRootCA.crt \
    && update-ca-certificates \
    && groupadd --system --gid 10001 tuneai \
    && useradd --system --uid 10001 --gid tuneai --create-home tuneai \
    && mkdir -p /data/uploads \
    && chown -R tuneai:tuneai /data /home/tuneai \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY deploy /opt/tuneai-deploy
COPY deploy/backend-entrypoint.sh /usr/local/bin/tuneai-entrypoint

RUN chmod 0555 /usr/local/bin/tuneai-entrypoint \
    && chown -R tuneai:tuneai /app

EXPOSE 8000
USER tuneai
ENTRYPOINT ["tuneai-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
