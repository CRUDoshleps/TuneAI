import os
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings, get_settings


class StorageService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate_upload(self, upload: UploadFile, content: bytes) -> None:
        normalized_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        if normalized_type not in self.settings.allowed_audio_types:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported audio type")
        if len(content) > self.settings.max_upload_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Audio file is too large")
        if not self._matches_audio_signature(normalized_type, content):
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Audio content does not match its type")

    def save_audio(self, answer_id: str, upload: UploadFile, content: bytes) -> str:
        self.validate_upload(upload, content)
        suffix = Path(upload.filename or "answer.webm").suffix or ".webm"
        object_key = f"answers/{answer_id}{suffix}"
        if self.settings.storage_backend == "s3":
            return self._save_s3(object_key, upload.content_type or "application/octet-stream", content)
        return self._save_local(object_key, content)

    @staticmethod
    def _matches_audio_signature(content_type: str, content: bytes) -> bool:
        if content_type == "audio/webm":
            return content.startswith(b"\x1a\x45\xdf\xa3")
        if content_type == "audio/ogg":
            return content.startswith(b"OggS")
        if content_type in {"audio/wav", "audio/x-wav"}:
            return len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WAVE"
        if content_type == "audio/mpeg":
            return content.startswith(b"ID3") or (len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0)
        if content_type == "audio/mp4":
            return len(content) >= 12 and content[4:8] == b"ftyp"
        return False

    def read_audio(self, object_key: str) -> bytes:
        if self.settings.storage_backend == "s3":
            client = self._s3_client()
            response = client.get_object(Bucket=self.settings.s3_bucket, Key=object_key)
            return response["Body"].read()
        path = Path(self.settings.upload_dir) / object_key
        return path.read_bytes()

    def save_source(self, source_id: str, filename: str, content_type: str, content: bytes) -> str:
        suffix = Path(filename).suffix.lower() or ".bin"
        object_key = f"sources/{source_id}{suffix}"
        if self.settings.storage_backend == "s3":
            return self._save_s3(object_key, content_type or "application/octet-stream", content)
        return self._save_local(object_key, content)

    def _save_local(self, object_key: str, content: bytes) -> str:
        path = Path(self.settings.upload_dir) / object_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return object_key

    def _save_s3(self, object_key: str, content_type: str, content: bytes) -> str:
        client = self._s3_client()
        client.put_object(Bucket=self.settings.s3_bucket, Key=object_key, Body=content, ContentType=content_type)
        return object_key

    def _s3_client(self):
        try:
            import boto3
            from botocore.client import Config
        except ImportError as exc:
            raise RuntimeError("S3 storage requires installing boto3") from exc
        endpoint = self.settings.s3_endpoint_url
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=self.settings.s3_access_key_id or os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=self.settings.s3_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=self.settings.s3_region,
            config=Config(signature_version="s3v4"),
        )
