"""Verify real Yandex AI credentials and the models used by TuneAI.

The script never prints the API key. Run it from the repository root after
creating `.env`:

    python scripts/yandex_smoke.py
"""

from __future__ import annotations

import asyncio
import argparse
import sys
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if not (BACKEND_ROOT / "app").is_dir() and Path("/app/app").is_dir():
    BACKEND_ROOT = Path("/app")
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings  # noqa: E402
from app.services.yandex import YandexAIClient  # noqa: E402


async def main(audio_output: Path | None = None) -> int:
    env_file = ROOT / ".env"
    settings = Settings(_env_file=env_file if env_file.is_file() else None)
    if settings.yandex_mock:
        print("error=YANDEX_MOCK is enabled")
        return 2
    if not settings.yandex_folder_id:
        print("error=YANDEX_FOLDER_ID is missing")
        return 2
    if not (settings.yandex_api_key or settings.yandex_iam_token):
        print("error=Yandex credentials are missing")
        return 2

    client = YandexAIClient(settings)
    try:
        embedding = await client.embed_query("TuneAI credential smoke test")
        evaluation = await client.evaluate_answer(
            question="Что такое машинное обучение?",
            expected_answer="Методы, которые обучают модели на данных.",
            transcript="Это методы, позволяющие компьютеру находить закономерности в данных.",
            criteria={"correctness": 1.0},
            rag_context=["Машинное обучение использует данные для настройки моделей."],
            max_score=5,
        )
        tts_headers = {"Authorization": client.auth_headers["Authorization"]}
        async with httpx.AsyncClient(timeout=120) as http:
            speech = await http.post(
                "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize",
                headers=tts_headers,
                data={
                    "text": (
                        "Машинное обучение позволяет компьютеру находить "
                        "закономерности в данных и делать прогнозы."
                    ),
                    "lang": "ru-RU",
                    "voice": "alena",
                    "format": "oggopus",
                },
            )
            speech.raise_for_status()
        transcript = await client.transcribe_audio(speech.content, "audio/ogg")
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:1000].replace("\n", " ")
        print(f"error=http_{exc.response.status_code}")
        print(f"service_response={body}")
        return 1
    except Exception as exc:
        print(f"error={type(exc).__name__}")
        print(f"details={exc}")
        return 1

    print("credentials=ok")
    print(f"embedding_dimensions={len(embedding)}")
    print(f"evaluation_score={evaluation.score}/{evaluation.max_score}")
    print(f"evaluation_confidence={evaluation.confidence}")
    print(f"speechkit_transcript_chars={len(transcript)}")
    if audio_output is not None:
        audio_output.parent.mkdir(parents=True, exist_ok=True)
        audio_output.write_bytes(speech.content)
        print(f"audio_output={audio_output}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-output", type=Path)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.audio_output)))
