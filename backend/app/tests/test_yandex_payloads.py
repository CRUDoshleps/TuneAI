from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.services import yandex
from app.services.yandex import YandexAIClient


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeAsyncClient:
    calls: list[tuple[str, dict]] = []

    def __init__(self, **_: object) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, url: str, *, json: dict, **_: object) -> FakeResponse:
        self.calls.append((url, json))
        if "recognizeFileAsync" in url:
            return FakeResponse({"text": "Распознанный ответ"})
        return FakeResponse(
            {
                "result": {
                    "alternatives": [
                        {
                            "message": {
                                "text": (
                                    '{"score": 8, "max_score": 10, "correct_points": [], '
                                    '"mistakes": [], "missing_points": [], "feedback": "ok", '
                                    '"recommendations": "next", "confidence": 0.9}'
                                )
                            }
                        }
                    ]
                }
            }
        )


class MetadataFakeAsyncClient:
    metadata_calls = 0
    post_headers: list[dict[str, str]] = []

    def __init__(self, **_: object) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str, *, headers: dict[str, str], **_: object) -> FakeResponse:
        assert "computeMetadata" in url
        assert headers == {"Metadata-Flavor": "Google"}
        self.__class__.metadata_calls += 1
        return FakeResponse({"access_token": "metadata-token", "expires_in": 3600})

    async def post(self, url: str, *, headers: dict[str, str], json: dict, **_: object) -> FakeResponse:
        self.__class__.post_headers.append(headers)
        assert "textEmbedding" in url
        assert json["text"]
        return FakeResponse({"embedding": [0.1, 0.2, 0.3]})


def real_settings() -> Settings:
    return Settings(
        yandex_mock=False,
        yandex_api_key="test-key",
        yandex_folder_id="test-folder",
    )


@pytest.mark.asyncio
async def test_metadata_iam_takes_precedence_over_stale_api_key_and_is_cached(monkeypatch):
    MetadataFakeAsyncClient.metadata_calls = 0
    MetadataFakeAsyncClient.post_headers = []
    monkeypatch.setattr(yandex.httpx, "AsyncClient", MetadataFakeAsyncClient)
    client = YandexAIClient(
        Settings(
            yandex_mock=False,
            yandex_api_key="stale-key",
            yandex_folder_id="test-folder",
            yandex_use_metadata_iam=True,
        )
    )

    assert await client.embed_query("first") == [0.1, 0.2, 0.3]
    assert await client.embed_query("second") == [0.1, 0.2, 0.3]

    assert MetadataFakeAsyncClient.metadata_calls == 1
    assert len(MetadataFakeAsyncClient.post_headers) == 2
    assert all(headers["Authorization"] == "Bearer metadata-token" for headers in MetadataFakeAsyncClient.post_headers)
    assert all(headers["x-folder-id"] == "test-folder" for headers in MetadataFakeAsyncClient.post_headers)


@pytest.mark.asyncio
async def test_completion_uses_rest_json_schema_casing(monkeypatch):
    FakeAsyncClient.calls = []
    monkeypatch.setattr(yandex.httpx, "AsyncClient", FakeAsyncClient)
    client = YandexAIClient(real_settings())

    result = await client.evaluate_answer(
        question="Что такое очередь?",
        expected_answer="Буфер сообщений",
        transcript="Это буфер.",
        criteria={},
        rag_context=["Материал"],
        max_score=10,
    )

    assert result.score == 8
    body = FakeAsyncClient.calls[0][1]
    assert "jsonSchema" in body
    assert "json_schema" not in body
    assert body["jsonSchema"]["schema"]["properties"]["score"]
    assert set(body["jsonSchema"]["schema"]["required"]) == set(
        body["jsonSchema"]["schema"]["properties"]
    )
    assert "review_recommended" not in body["jsonSchema"]["schema"]["properties"]


@pytest.mark.asyncio
async def test_speechkit_request_uses_rest_camel_case(monkeypatch):
    FakeAsyncClient.calls = []
    monkeypatch.setattr(yandex.httpx, "AsyncClient", FakeAsyncClient)
    client = YandexAIClient(real_settings())

    transcript = await client.transcribe_audio(b"wav-bytes", "audio/wav")

    assert transcript == "Распознанный ответ"
    body = FakeAsyncClient.calls[0][1]
    assert "recognitionModel" in body
    assert "recognition_model" not in body
    assert body["recognitionModel"]["audioFormat"] == {
        "containerAudio": {"containerAudioType": "WAV"}
    }


@pytest.mark.asyncio
async def test_webm_is_converted_to_supported_ogg_opus(monkeypatch):
    client = YandexAIClient(real_settings())
    transcode = AsyncMock(return_value=b"ogg-bytes")
    monkeypatch.setattr(client, "_transcode_to_ogg", transcode)

    audio, audio_format = await client._prepare_speechkit_audio(
        b"webm-bytes", "audio/webm;codecs=opus"
    )

    assert audio == b"ogg-bytes"
    assert audio_format == {"containerAudio": {"containerAudioType": "OGG_OPUS"}}
    transcode.assert_awaited_once_with(b"webm-bytes")


@pytest.mark.asyncio
async def test_unknown_audio_type_is_rejected_before_external_call():
    client = YandexAIClient(real_settings())

    with pytest.raises(ValueError, match="Unsupported audio type"):
        await client._prepare_speechkit_audio(b"data", "audio/flac")


def test_speechkit_v3_concatenated_results_prefer_normalized_text():
    raw = (
        '{"result":{"final":{"alternatives":[{"text":"черновой текст"}]}}}\n'
        '{"result":{"finalRefinement":{"normalizedText":{"alternatives":'
        '[{"text":"Итоговый текст."}]}}}}'
    )

    payloads = YandexAIClient._decode_json_stream(raw)

    assert YandexAIClient._extract_transcript(payloads) == "Итоговый текст."
