from types import SimpleNamespace

from app.core.config import Settings
from app.services.storage import StorageService


def test_browser_audio_codec_parameter_is_accepted():
    storage = StorageService(
        Settings(
            allowed_audio_types=["audio/webm"],
        )
    )
    upload = SimpleNamespace(
        content_type="audio/webm;codecs=opus",
        filename="answer.webm",
    )

    storage.validate_upload(upload, b"webm")
