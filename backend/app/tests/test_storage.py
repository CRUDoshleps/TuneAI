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

    storage.validate_upload(upload, b"\x1a\x45\xdf\xa3webm")


def test_disguised_audio_content_is_rejected():
    storage = StorageService(Settings(allowed_audio_types=["audio/webm"]))
    upload = SimpleNamespace(content_type="audio/webm", filename="answer.webm")

    try:
        storage.validate_upload(upload, b"not really webm")
    except Exception as exception:
        assert getattr(exception, "status_code", None) == 415
    else:
        raise AssertionError("Disguised audio must be rejected")
