from functools import lru_cache
import json
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    secret_key: str = Field(default="dev-secret-change-me", min_length=16)
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    cors_origin_regex: str | None = None
    cors_allow_credentials: bool = True
    rate_limit_per_minute: int = 60

    database_url: str = "sqlite:///./tuneai.db"

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    queue_name: str = "tuneai.answer.uploaded"

    upload_dir: str = "./uploads"
    max_upload_mb: int = 50
    allowed_audio_types: Annotated[list[str], NoDecode] = [
        "audio/webm",
        "audio/ogg",
        "audio/mpeg",
        "audio/mp4",
        "audio/wav",
        "audio/x-wav",
    ]

    storage_backend: Literal["local", "s3"] = "local"
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_bucket: str = "tuneai-audio"
    s3_region: str = "us-east-1"

    yandex_mock: bool = True
    yandex_folder_id: str | None = None
    yandex_api_key: str | None = None
    yandex_iam_token: str | None = None
    yandex_gpt_model_uri: str | None = None
    yandex_lite_model_uri: str | None = None
    yandex_embed_doc_uri: str | None = None
    yandex_embed_query_uri: str | None = None
    yandex_completion_url: str = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    yandex_embedding_url: str = "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding"
    speechkit_recognize_url: str = "https://stt.api.cloud.yandex.net/stt/v3/recognizeFileAsync"
    speechkit_operation_url: str = "https://operation.api.cloud.yandex.net/operations"
    yandex_data_logging_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", "allowed_audio_types", mode="before")
    @classmethod
    def split_csv_or_json(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                loaded = json.loads(stripped)
                if not isinstance(loaded, list):
                    raise ValueError("Expected a JSON array")
                return [str(item).strip().rstrip("/") for item in loaded if str(item).strip()]
            return [item.strip().rstrip("/") for item in stripped.split(",") if item.strip()]
        return value

    @property
    def normalized_cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins if origin.strip()]

    @property
    def effective_cors_allow_credentials(self) -> bool:
        return self.cors_allow_credentials and "*" not in self.normalized_cors_origins

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def gpt_model_uri(self) -> str:
        if self.yandex_gpt_model_uri:
            return self.yandex_gpt_model_uri
        folder = self.yandex_folder_id or "<folder_ID>"
        return f"gpt://{folder}/yandexgpt-5.1"

    @property
    def lite_model_uri(self) -> str:
        if self.yandex_lite_model_uri:
            return self.yandex_lite_model_uri
        folder = self.yandex_folder_id or "<folder_ID>"
        return f"gpt://{folder}/yandexgpt-5-lite"

    @property
    def embed_doc_uri(self) -> str:
        if self.yandex_embed_doc_uri:
            return self.yandex_embed_doc_uri
        folder = self.yandex_folder_id or "<folder_ID>"
        return f"emb://{folder}/text-embeddings-v2-doc/"

    @property
    def embed_query_uri(self) -> str:
        if self.yandex_embed_query_uri:
            return self.yandex_embed_query_uri
        folder = self.yandex_folder_id or "<folder_ID>"
        return f"emb://{folder}/text-embeddings-v2-query/"


@lru_cache
def get_settings() -> Settings:
    return Settings()
