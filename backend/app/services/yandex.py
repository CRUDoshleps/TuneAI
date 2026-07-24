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

        body = {
            "content": base64.b64encode(audio).decode("ascii"),
            "recognition_model": {
                "model": "general",
                "audio_format": self._speechkit_audio_format(content_type),
                "text_normalization": {"text_normalization": "TEXT_NORMALIZATION_ENABLED"},
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
                    return self._extract_transcript(payload.get("response", payload))
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
            "You are an expert examiner. Grade a spoken answer strictly against the rubric and source context. "
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
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(self.settings.yandex_completion_url, headers=self.auth_headers, json=body)
            response.raise_for_status()
            text = self._extract_completion_text(response.json())
        return EvaluationResult.model_validate_json(self._extract_json(text))

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

    @staticmethod
    def _speechkit_audio_format(content_type: str | None) -> dict[str, Any]:
        if content_type == "audio/wav" or content_type == "audio/x-wav":
            return {"container_audio": {"container_audio_type": "WAV"}}
        if content_type == "audio/mpeg":
            return {"container_audio": {"container_audio_type": "MP3"}}
        if content_type == "audio/ogg":
            return {"container_audio": {"container_audio_type": "OGG_OPUS"}}
        return {"container_audio": {"container_audio_type": "WEBM_OPUS"}}

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
    def _extract_transcript(payload: dict[str, Any]) -> str:
        texts: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if isinstance(node.get("text"), str):
                    texts.append(node["text"])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        transcript = " ".join(dict.fromkeys(texts))
        if not transcript:
            raise RuntimeError("SpeechKit response did not include transcript text")
        return transcript

