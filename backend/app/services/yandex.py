import asyncio
import base64
import hashlib
import json
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.schemas import EvaluationResult


class YandexAIClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def auth_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "x-data-logging-enabled": str(self.settings.yandex_data_logging_enabled).lower(),
        }
        if self.settings.yandex_api_key:
            headers["Authorization"] = f"Api-Key {self.settings.yandex_api_key}"
        elif self.settings.yandex_iam_token:
            headers["Authorization"] = f"Bearer {self.settings.yandex_iam_token}"
        if self.settings.yandex_folder_id:
            headers["x-folder-id"] = self.settings.yandex_folder_id
        return headers

    async def transcribe_audio(self, audio: bytes, content_type: str | None) -> str:
        if self.settings.yandex_mock or not (self.settings.yandex_api_key or self.settings.yandex_iam_token):
            return "Mock transcript: the learner gives a partially correct spoken answer."

        speechkit_audio, audio_format = await self._prepare_speechkit_audio(audio, content_type)
        body = {
            "content": base64.b64encode(speechkit_audio).decode("ascii"),
            "recognitionModel": {
                "model": "general",
                "audioFormat": audio_format,
                "textNormalization": {"textNormalization": "TEXT_NORMALIZATION_ENABLED"},
            },
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(self.settings.speechkit_recognize_url, headers=self.auth_headers, json=body)
            response.raise_for_status()
            operation = response.json()
            operation_id = operation.get("id")
            if not operation_id:
                return self._extract_transcript(operation)
            for _ in range(60):
                result = await client.get(
                    f"{self.settings.speechkit_operation_url.rstrip('/')}/{operation_id}", headers=self.auth_headers
                )
                result.raise_for_status()
                payload = result.json()
                if payload.get("done"):
                    recognition = await client.get(
                        self.settings.speechkit_result_url,
                        headers=self.auth_headers,
                        params={"operation_id": operation_id},
                    )
                    recognition.raise_for_status()
                    return self._extract_transcript(
                        self._decode_json_stream(recognition.text)
                    )
                await asyncio.sleep(2)
        raise RuntimeError("SpeechKit recognition timed out")

    async def embed_query(self, text: str) -> list[float]:
        return await self._embed(text, self.settings.embed_query_uri)

    async def embed_document(self, text: str) -> list[float]:
        return await self._embed(text, self.settings.embed_doc_uri)

    async def evaluate_answer(
        self,
        *,
        question: str,
        expected_answer: str,
        transcript: str,
        criteria: dict[str, Any],
        rag_context: list[str],
        max_score: float,
    ) -> EvaluationResult:
        if self.settings.yandex_mock or not (self.settings.yandex_api_key or self.settings.yandex_iam_token):
            confidence = 0.72
            score = max(1.0, round(max_score * 0.68, 2))
            return EvaluationResult(
                score=score,
                max_score=max_score,
                correct_points=["The answer addresses the question at a high level."],
                mistakes=["Mock mode cannot verify domain facts against the real Yandex model."],
                missing_points=["Add concrete definitions, examples, and links to the provided materials."],
                feedback="The response is understandable but incomplete. Use the rubric and source materials to expand it.",
                recommendations="Repeat the relevant material and answer with a structured thesis, explanation, and example.",
                confidence=confidence,
            )

        system_prompt = (
            "You are an educational feedback assistant, not a replacement for a teacher. "
            "Grade a spoken answer strictly against the rubric and source context. "
            "Do not invent facts outside the supplied context. If evidence is insufficient, lower confidence. "
            "Return only valid JSON with fields: score, max_score, correct_points, mistakes, missing_points, "
            "feedback, recommendations, confidence."
        )
        user_prompt = {
            "question": question,
            "expected_answer": expected_answer,
            "spoken_answer_transcript": transcript,
            "criteria": criteria,
            "rag_context": rag_context,
            "max_score": max_score,
        }
        body = {
            "modelUri": self.settings.gpt_model_uri,
            "completionOptions": {"stream": False, "temperature": 0.1, "maxTokens": "2000"},
            "messages": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": json.dumps(user_prompt, ensure_ascii=False)},
            ],
            "jsonSchema": {"schema": self._evaluation_response_schema()},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(self.settings.yandex_completion_url, headers=self.auth_headers, json=body)
            response.raise_for_status()
            text = self._extract_completion_text(response.json())
        return EvaluationResult.model_validate_json(self._extract_json(text))

    @staticmethod
    def _evaluation_response_schema() -> dict[str, Any]:
        """Return the strict schema accepted by Yandex structured output.

        Explainability and review fields are added deterministically by the
        processing service, so the model should only generate grading fields.
        Yandex requires every schema property to be listed as required.
        """
        generated_fields = [
            "score",
            "max_score",
            "correct_points",
            "mistakes",
            "missing_points",
            "feedback",
            "recommendations",
            "confidence",
        ]
        schema = EvaluationResult.model_json_schema()
        schema["properties"] = {
            field: schema["properties"][field] for field in generated_fields
        }
        schema["required"] = generated_fields
        schema["additionalProperties"] = False
        return schema

    async def _embed(self, text: str, model_uri: str) -> list[float]:
        if self.settings.yandex_mock or not (self.settings.yandex_api_key or self.settings.yandex_iam_token):
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            values = [((digest[i % len(digest)] / 255.0) * 2) - 1 for i in range(64)]
            return values

        body = {"modelUri": model_uri, "text": text[:8000]}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self.settings.yandex_embedding_url, headers=self.auth_headers, json=body)
            response.raise_for_status()
            payload = response.json()
        embedding = payload.get("embedding") or payload.get("result", {}).get("embedding")
        if not embedding:
            raise RuntimeError("Yandex embedding response did not include an embedding")
        return [float(value) for value in embedding]

    async def _prepare_speechkit_audio(
        self, audio: bytes, content_type: str | None
    ) -> tuple[bytes, dict[str, Any]]:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        if normalized_type in {"audio/wav", "audio/x-wav"}:
            return audio, {"containerAudio": {"containerAudioType": "WAV"}}
        if normalized_type == "audio/mpeg":
            return audio, {"containerAudio": {"containerAudioType": "MP3"}}
        if normalized_type in {"audio/ogg", "application/ogg"}:
            return audio, {"containerAudio": {"containerAudioType": "OGG_OPUS"}}
        if normalized_type in {"audio/webm", "video/webm", "audio/mp4", "video/mp4"}:
            converted = await self._transcode_to_ogg(audio)
            return converted, {"containerAudio": {"containerAudioType": "OGG_OPUS"}}
        raise ValueError(f"Unsupported audio type for SpeechKit: {content_type or 'unknown'}")

    @staticmethod
    async def _transcode_to_ogg(audio: bytes) -> bytes:
        try:
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-vn",
                "-c:a",
                "libopus",
                "-f",
                "ogg",
                "pipe:1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("ffmpeg is required to convert browser audio for SpeechKit") from exc
        stdout, stderr = await process.communicate(audio)
        if process.returncode != 0 or not stdout:
            details = stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(f"Could not convert browser audio to OGG Opus: {details}")
        return stdout

    @staticmethod
    def _extract_completion_text(payload: dict[str, Any]) -> str:
        alternatives = payload.get("result", {}).get("alternatives", [])
        if alternatives:
            return alternatives[0].get("message", {}).get("text", "")
        return payload.get("text", "")

    @staticmethod
    def _extract_json(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("LLM response did not contain JSON")
        return stripped[start : end + 1]

    @staticmethod
    def _decode_json_stream(raw: str) -> list[Any]:
        """Decode the concatenated JSON objects returned by SpeechKit v3."""
        decoder = json.JSONDecoder()
        position = 0
        payloads: list[Any] = []
        while position < len(raw):
            while position < len(raw) and raw[position].isspace():
                position += 1
            if position >= len(raw):
                break
            payload, position = decoder.raw_decode(raw, position)
            payloads.append(payload)
        return payloads

    @staticmethod
    def _extract_transcript(payload: Any) -> str:
        refined: list[str] = []
        final: list[str] = []
        generic: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if isinstance(node.get("text"), str):
                    generic.append(node["text"])
                refinement = node.get("finalRefinement")
                if isinstance(refinement, dict):
                    normalized = refinement.get("normalizedText", {})
                    for alternative in normalized.get("alternatives", []):
                        if isinstance(alternative.get("text"), str):
                            refined.append(alternative["text"])
                final_result = node.get("final")
                if isinstance(final_result, dict):
                    for alternative in final_result.get("alternatives", []):
                        if isinstance(alternative.get("text"), str):
                            final.append(alternative["text"])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        transcript = " ".join(dict.fromkeys(refined or final or generic))
        if not transcript:
            raise RuntimeError("SpeechKit response did not include transcript text")
        return transcript

