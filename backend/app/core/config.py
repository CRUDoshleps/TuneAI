from functools import lru_cache
import json
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    secret_key: str = Field(default="dev-secret-change-me", min_length=16)
    docs_enabled: bool = True
    metrics_enabled: bool = True
    init_db_on_startup: bool = True
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
    demo_bootstrap_enabled: bool = True
    demo_bootstrap_limit_per_hour: int = 30
    demo_bootstrap_ttl_hours: int = 24

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
    test_creator_roles: Annotated[list[str], NoDecode] = ["student", "methodist", "teacher", "interviewer", "admin"]
    answer_reviewer_roles: Annotated[list[str], NoDecode] = ["teacher", "interviewer", "admin"]
    tuneai_template: str = Field(default="unconfigured", validation_alias=AliasChoices("TUNEAI_TEMPLATE", "NEXT_PUBLIC_TUNEAI_TEMPLATE"))
    tuneai_product_name: str = Field(
        default="Self-host Test Platform",
        validation_alias=AliasChoices("TUNEAI_PRODUCT_NAME", "NEXT_PUBLIC_TUNEAI_PRODUCT_NAME"),
    )
    tuneai_logo_text: str = Field(default="Demo", validation_alias=AliasChoices("TUNEAI_LOGO_TEXT", "NEXT_PUBLIC_TUNEAI_LOGO_TEXT"))
    tuneai_logo_url: str | None = Field(default=None, validation_alias=AliasChoices("TUNEAI_LOGO_URL", "NEXT_PUBLIC_TUNEAI_LOGO_URL"))
    tuneai_repository_url: str = Field(
        default="https://github.com/CRUDoshleps/TuneAI",
        validation_alias=AliasChoices("TUNEAI_REPOSITORY_URL", "NEXT_PUBLIC_TUNEAI_REPOSITORY_URL"),
    )
    tuneai_docs_url: str = Field(
        default="https://github.com/CRUDoshleps/TuneAI",
        validation_alias=AliasChoices("TUNEAI_DOCS_URL", "NEXT_PUBLIC_TUNEAI_DOCS_URL"),
    )
    tuneai_consultation_email: str = Field(
        default="admin@example.com",
        validation_alias=AliasChoices("TUNEAI_CONSULTATION_EMAIL", "NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL"),
    )
    tuneai_consultation_person: str = Field(
        default="Implementation owner",
        validation_alias=AliasChoices("TUNEAI_CONSULTATION_PERSON", "NEXT_PUBLIC_TUNEAI_CONSULTATION_PERSON"),
    )
    tuneai_config_json: str | None = Field(default=None, validation_alias=AliasChoices("TUNEAI_CONFIG_JSON", "NEXT_PUBLIC_TUNEAI_CONFIG_JSON"))

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
    yandex_completion_url: str = "https://ai.api.cloud.yandex.net/foundationModels/v1/completion"
    yandex_embedding_url: str = "https://ai.api.cloud.yandex.net/foundationModels/v1/textEmbedding"
    speechkit_recognize_url: str = "https://stt.api.cloud.yandex.net/stt/v3/recognizeFileAsync"
    speechkit_operation_url: str = "https://operation.api.cloud.yandex.net/operations"
    speechkit_result_url: str = "https://stt.api.cloud.yandex.net/stt/v3/getRecognition"
    yandex_data_logging_enabled: bool = False
    review_confidence_threshold: float = Field(default=0.75, ge=0, le=1)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", "allowed_audio_types", "test_creator_roles", "answer_reviewer_roles", mode="before")
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

    def validate_production(self) -> None:
        if self.app_env != "production":
            return
        errors: list[str] = []
        if self.secret_key == "dev-secret-change-me":
            errors.append("SECRET_KEY must be changed")
        if self.yandex_mock:
            errors.append("YANDEX_MOCK must be false")
        if self.demo_bootstrap_enabled:
            errors.append("DEMO_BOOTSTRAP_ENABLED must be false")
        if not (self.yandex_api_key or self.yandex_iam_token):
            errors.append("Yandex credentials are required")
        if not self.yandex_folder_id:
            errors.append("YANDEX_FOLDER_ID is required")
        if errors:
            raise RuntimeError("Invalid production configuration: " + "; ".join(errors))

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
        return f"emb://{folder}/text-search-doc/latest"

    @property
    def embed_query_uri(self) -> str:
        if self.yandex_embed_query_uri:
            return self.yandex_embed_query_uri
        folder = self.yandex_folder_id or "<folder_ID>"
        return f"emb://{folder}/text-search-query/latest"


@lru_cache
def get_settings() -> Settings:
    return Settings()
